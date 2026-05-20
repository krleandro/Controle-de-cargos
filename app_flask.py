import sqlite3, os, traceback
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_file, render_template, abort

from relatorio_pdf import gerar_relatorio

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR))
DB_PATH  = DATA_DIR / "quadro_pessoal.db"
HTML_DIR = BASE_DIR / "static"

if not DB_PATH.exists():
    raise SystemExit(
        f"\n[ERRO] Banco não encontrado: {DB_PATH.name}\n"
        "Execute primeiro:  python criar_banco.py\n"
        "Ou use o iniciar.bat que faz isso automaticamente."
    )

# ── App ────────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static", template_folder="static")

# ── Banco ──────────────────────────────────────────────────────────────────────
def get_db_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

# ── Handler global de exceções ─────────────────────────────────────────────────
@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    print(f"[ERRO] {request.url}: {e}\n{tb}")
    return jsonify({"detail": str(e), "tipo": type(e).__name__}), 500

# ── Rotas de dados ─────────────────────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """KPIs do painel principal."""
    con = get_db_connection()
    try:
        r = con.execute("""
            SELECT
              COUNT(*)                                           AS total_cargos,
              COALESCE(SUM(total_previstos), 0)                 AS total_previstos,
              COALESCE(SUM(total_ocupados), 0)                  AS total_ocupados,
              COALESCE(SUM(saldo_vagas), 0)                     AS total_saldo,
              COALESCE(SUM(alerta_saldo_negativo), 0)           AS alertas,
              SUM(CASE situacao WHEN 'Em vigor' THEN 1 ELSE 0 END) AS em_vigor,
              SUM(CASE situacao WHEN 'Extinto'  THEN 1 ELSE 0 END) AS extintos,
              SUM(CASE tipo_provimento WHEN 'Efetivo'  THEN 1 ELSE 0 END) AS efetivos,
              SUM(CASE tipo_provimento WHEN 'Comissão' THEN 1 ELSE 0 END) AS comissao
            FROM vw_SaldoVagas
        """).fetchone()
        return jsonify(dict(r))
    finally:
        con.close()

@app.route("/api/cargos", methods=["GET"])
def listar_cargos():
    """Lista todos os cargos com saldo calculado."""
    situacao = request.args.get("situacao")
    tipo = request.args.get("tipo")
    q = request.args.get("q")
    
    sql = "SELECT * FROM vw_SaldoVagas WHERE 1=1"
    params = []
    if situacao and situacao != "Todos":
        sql += " AND situacao = ?"; params.append(situacao)
    if tipo and tipo != "Todos":
        sql += " AND tipo_provimento = ?"; params.append(tipo)
    if q:
        sql += " AND (nome LIKE ? OR codigo_fopag LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY nome COLLATE NOCASE"
    
    con = get_db_connection()
    try:
        rows = con.execute(sql, params).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>", methods=["GET"])
def get_cargo(cargo_id):
    """Retorna um cargo com suas leis e fontes de carga horária."""
    con = get_db_connection()
    try:
        cargo = con.execute("SELECT * FROM vw_SaldoVagas WHERE id = ?", (cargo_id,)).fetchone()
        if not cargo:
            abort(404, description="Cargo não encontrado")

        leis = con.execute(
            "SELECT * FROM LeisPertinentes WHERE cargo_id = ? ORDER BY ano, numero",
            (cargo_id,)
        ).fetchall()

        fontes = con.execute(
            "SELECT * FROM FontesCargaHoraria WHERE cargo_id = ?",
            (cargo_id,)
        ).fetchall()

        return jsonify({
            "cargo":  dict(cargo),
            "leis":   [dict(l) for l in leis],
            "fontes": [dict(f) for f in fontes],
        })
    finally:
        con.close()

@app.route("/api/cargos", methods=["POST"])
def criar_cargo():
    """Cria um novo cargo no quadro."""
    dados = request.get_json()
    con = get_db_connection()
    try:
        cur = con.execute("""
            INSERT INTO Cargos
              (nome, codigo_fopag, situacao, situacao_delib, tipo_provimento, escolaridade,
               carga_horaria, simbolo_vencimento, total_previstos, total_ocupados, atribuicoes,
               recrutamento, restricao_exigencia, fonte_carga_horaria, fonte_atribuicoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            dados.get("nome"), dados.get("codigo_fopag"), dados.get("situacao", "Em vigor"),
            dados.get("situacao_delib", "não enviado"), dados.get("tipo_provimento", "Efetivo"),
            dados.get("escolaridade"), dados.get("carga_horaria"), dados.get("simbolo_vencimento"),
            dados.get("total_previstos", 0), dados.get("total_ocupados", 0), dados.get("atribuicoes"),
            dados.get("recrutamento"), dados.get("restricao_exigencia"),
            dados.get("fonte_carga_horaria"), dados.get("fonte_atribuicoes")
        ))
        con.commit()
        return jsonify({"id": cur.lastrowid, "mensagem": "Cargo criado com sucesso."}), 201
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>", methods=["PUT"])
def atualizar_cargo(cargo_id):
    """Atualiza os dados de um cargo existente."""
    dados = request.get_json()
    con = get_db_connection()
    try:
        cargo = con.execute("SELECT id FROM Cargos WHERE id=?", (cargo_id,)).fetchone()
        if not cargo:
            abort(404, description="Cargo não encontrado")
        con.execute("""
            UPDATE Cargos SET
              nome=?, codigo_fopag=?, situacao=?, situacao_delib=?, tipo_provimento=?, escolaridade=?,
              carga_horaria=?, simbolo_vencimento=?, total_previstos=?,
              total_ocupados=?, atribuicoes=?, recrutamento=?, restricao_exigencia=?,
              fonte_carga_horaria=?, fonte_atribuicoes=?
            WHERE id=?
        """, (
            dados.get("nome"), dados.get("codigo_fopag"), dados.get("situacao"),
            dados.get("situacao_delib"), dados.get("tipo_provimento"),
            dados.get("escolaridade"), dados.get("carga_horaria"), dados.get("simbolo_vencimento"),
            dados.get("total_previstos"), dados.get("total_ocupados"), dados.get("atribuicoes"),
            dados.get("recrutamento"), dados.get("restricao_exigencia"),
            dados.get("fonte_carga_horaria"), dados.get("fonte_atribuicoes"), cargo_id
        ))
        con.commit()
        return jsonify({"mensagem": "Cargo atualizado."})
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>/ocupados", methods=["PATCH"])
def atualizar_ocupados(cargo_id):
    """Atualiza somente o total de vagas ocupadas."""
    dados = request.get_json()
    con = get_db_connection()
    try:
        cargo = con.execute("SELECT total_previstos FROM Cargos WHERE id=?", (cargo_id,)).fetchone()
        if not cargo:
            abort(404, description="Cargo não encontrado")
            
        total_ocupados = max(0, dados.get("total_ocupados", 0))
        con.execute(
            "UPDATE Cargos SET total_ocupados=? WHERE id=?",
            (total_ocupados, cargo_id)
        )
        con.commit()
        saldo = cargo["total_previstos"] - total_ocupados
        return jsonify({"saldo_novo": saldo})
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>/leis", methods=["POST"])
def registrar_lei(cargo_id):
    """Registra uma lei pertinente."""
    lei = request.get_json()
    ACOES_COM_QTD = {"Cria", "Extingue", "Fixa"}
    ACOES_VALIDAS = {"Cria", "Extingue", "Fixa", "Altera", "Regulamenta", "Outro"}
    
    acao = lei.get("acao")
    quantidade = lei.get("quantidade")

    if acao not in ACOES_VALIDAS:
        abort(400, description=f"Ação inválida: {acao}")
    if acao in ACOES_COM_QTD and quantidade is None:
        abort(400, description=f"Ação '{acao}' exige o campo 'quantidade'.")

    con = get_db_connection()
    try:
        cargo = con.execute(
            "SELECT id, nome, total_previstos, total_ocupados FROM Cargos WHERE id=?",
            (cargo_id,)
        ).fetchone()
        if not cargo:
            abort(404, description="Cargo não encontrado")

        prev_antes = cargo["total_previstos"]

        if acao == "Cria":
            novo_prev = prev_antes + quantidade
        elif acao == "Extingue":
            novo_prev = max(0, prev_antes - quantidade)
        elif acao == "Fixa":
            novo_prev = quantidade
        else:
            novo_prev = prev_antes

        if novo_prev != prev_antes:
            con.execute(
                "UPDATE Cargos SET total_previstos=? WHERE id=?",
                (novo_prev, cargo_id)
            )

        cur = con.execute("""
            INSERT INTO LeisPertinentes
              (cargo_id, numero, ano, descricao, acao, quantidade)
            VALUES (?,?,?,?,?,?)
        """, (cargo_id, lei.get("numero"), lei.get("ano"), lei.get("descricao"), acao,
              quantidade if acao in ACOES_COM_QTD else None))
              
        con.commit()

        saldo_novo = novo_prev - cargo["total_ocupados"]
        return jsonify({
            "lei_id":          cur.lastrowid,
            "saldo_anterior":  prev_antes - cargo["total_ocupados"],
            "saldo_novo":      saldo_novo,
            "total_previstos": novo_prev,
            "mensagem":        f"Lei {lei.get('numero')}/{lei.get('ano')} registrada. Saldo: {saldo_novo:+d}",
        }), 201
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>/leis/<int:lei_id>", methods=["PUT"])
def atualizar_lei(cargo_id, lei_id):
    """Atualiza uma lei pertinente."""
    lei = request.get_json()
    ACOES_COM_QTD = {"Cria", "Extingue", "Fixa"}
    ACOES_VALIDAS = {"Cria", "Extingue", "Fixa", "Altera", "Regulamenta", "Outro"}
    
    acao = lei.get("acao")
    quantidade = lei.get("quantidade")

    if acao not in ACOES_VALIDAS:
        abort(400, description=f"Ação inválida: {acao}")
    if acao in ACOES_COM_QTD and quantidade is None:
        abort(400, description=f"Ação '{acao}' exige o campo 'quantidade'.")

    con = get_db_connection()
    try:
        # Pega a lei antiga para reverter o impacto no cargo
        lei_antiga = con.execute("SELECT acao, quantidade FROM LeisPertinentes WHERE id=? AND cargo_id=?", (lei_id, cargo_id)).fetchone()
        if not lei_antiga:
            abort(404, description="Lei não encontrada")

        cargo = con.execute("SELECT id, total_previstos, total_ocupados FROM Cargos WHERE id=?", (cargo_id,)).fetchone()
        
        # Desfaz o impacto da lei antiga
        prev_atual = cargo["total_previstos"]
        acao_antiga = lei_antiga["acao"]
        qtd_antiga = lei_antiga["quantidade"] or 0
        
        if acao_antiga == "Cria":
            prev_atual = max(0, prev_atual - qtd_antiga)
        elif acao_antiga == "Extingue":
            prev_atual = prev_atual + qtd_antiga
        # Se era "Fixa", não temos como saber o valor anterior, então ignoramos o desfazimento.

        # Aplica o impacto da nova lei
        if acao == "Cria":
            novo_prev = prev_atual + quantidade
        elif acao == "Extingue":
            novo_prev = max(0, prev_atual - quantidade)
        elif acao == "Fixa":
            novo_prev = quantidade
        else:
            novo_prev = prev_atual

        if novo_prev != cargo["total_previstos"]:
            con.execute("UPDATE Cargos SET total_previstos=? WHERE id=?", (novo_prev, cargo_id))

        con.execute("""
            UPDATE LeisPertinentes SET
              numero=?, ano=?, descricao=?, acao=?, quantidade=?
            WHERE id=? AND cargo_id=?
        """, (lei.get("numero"), lei.get("ano"), lei.get("descricao"), acao,
              quantidade if acao in ACOES_COM_QTD else None, lei_id, cargo_id))
              
        con.commit()
        return jsonify({"mensagem": "Lei atualizada com sucesso."})
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>/leis/<int:lei_id>", methods=["DELETE"])
def deletar_lei(cargo_id, lei_id):
    """Deleta uma lei pertinente."""
    con = get_db_connection()
    try:
        lei_antiga = con.execute("SELECT acao, quantidade FROM LeisPertinentes WHERE id=? AND cargo_id=?", (lei_id, cargo_id)).fetchone()
        if not lei_antiga:
            abort(404, description="Lei não encontrada")

        cargo = con.execute("SELECT id, total_previstos FROM Cargos WHERE id=?", (cargo_id,)).fetchone()
        
        prev_atual = cargo["total_previstos"]
        acao_antiga = lei_antiga["acao"]
        qtd_antiga = lei_antiga["quantidade"] or 0
        
        if acao_antiga == "Cria":
            prev_atual = max(0, prev_atual - qtd_antiga)
        elif acao_antiga == "Extingue":
            prev_atual = prev_atual + qtd_antiga

        if prev_atual != cargo["total_previstos"]:
            con.execute("UPDATE Cargos SET total_previstos=? WHERE id=?", (prev_atual, cargo_id))

        con.execute("DELETE FROM LeisPertinentes WHERE id=? AND cargo_id=?", (lei_id, cargo_id))
        con.commit()
        return jsonify({"mensagem": "Lei excluída com sucesso."})
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>/leis", methods=["GET"])
def listar_leis(cargo_id):
    con = get_db_connection()
    try:
        leis = con.execute(
            "SELECT * FROM LeisPertinentes WHERE cargo_id=? ORDER BY ano, CAST(numero AS INTEGER)",
            (cargo_id,)
        ).fetchall()
        return jsonify([dict(l) for l in leis])
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>/relatorio", methods=["GET"])
def baixar_relatorio(cargo_id):
    con = get_db_connection()
    try:
        cargo = con.execute("SELECT * FROM vw_SaldoVagas WHERE id = ?", (cargo_id,)).fetchone()
        if not cargo:
            abort(404, description="Cargo não encontrado")

        leis = con.execute(
            "SELECT * FROM LeisPertinentes WHERE cargo_id = ? ORDER BY ano, CAST(numero AS INTEGER)",
            (cargo_id,)
        ).fetchall()

        fontes = con.execute("SELECT * FROM FontesCargaHoraria WHERE cargo_id = ?", (cargo_id,)).fetchall()
    finally:
        con.close()

    import io
    try:
        pdf_bytes = gerar_relatorio(dict(cargo), [dict(l) for l in leis], [dict(f) for f in fontes])
    except Exception as e:
        abort(500, description=f"Erro ao gerar PDF: {e}")

    import re
    safe_name = re.sub(r'[^\w\s-]', '', dict(cargo)['nome']).strip().replace(' ', '_')
    filename = f"Relatorio_FOPAG_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route("/")
def index():
    with open(HTML_DIR / "index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return html_content

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
