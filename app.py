import sqlite3, os, traceback
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_file, render_template, abort

from relatorio_pdf import gerar_relatorio, gerar_relatorio_consolidado

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

# ── Migração: Criar tabela Ocupantes e triggers se não existirem ──────────────
def executar_migracao():
    con = sqlite3.connect(DB_PATH)
    try:
        r = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Ocupantes'").fetchone()
        if not r:
            print("[MIGRAÇÃO] Criando tabela Ocupantes e triggers...")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS Ocupantes (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    cargo_id                INTEGER NOT NULL REFERENCES Cargos (id) ON DELETE CASCADE,
                    nome                    TEXT    NOT NULL,
                    matricula               TEXT    NOT NULL,
                    tipo_recrutamento       TEXT    CHECK (tipo_recrutamento IN ('Amplo', 'Limitado', 'Outro', NULL)),
                    simbolo_vencimento      TEXT    CHECK (simbolo_vencimento IN ('SS', 'SP', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5', 'CC6', 'FGDE 1', 'FGDE 2', 'FGDE 3', 'FGDE 4', 'FGDE 5', 'FGDE 6', NULL)),
                    portaria                TEXT,
                    boletim_oficial         TEXT,
                    data_nomeacao           TEXT,    -- YYYY-MM-DD
                    criado_em               TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                    atualizado_em           TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
                );
                
                CREATE INDEX IF NOT EXISTS idx_ocupantes_cargo_id ON Ocupantes (cargo_id);
                
                CREATE TRIGGER IF NOT EXISTS trg_ocupantes_insert AFTER INSERT ON Ocupantes
                BEGIN
                    UPDATE Cargos
                    SET total_ocupados = (SELECT COUNT(*) FROM Ocupantes WHERE cargo_id = NEW.cargo_id)
                    WHERE id = NEW.cargo_id;
                END;

                CREATE TRIGGER IF NOT EXISTS trg_ocupantes_delete AFTER DELETE ON Ocupantes
                BEGIN
                    UPDATE Cargos
                    SET total_ocupados = (SELECT COUNT(*) FROM Ocupantes WHERE cargo_id = OLD.cargo_id)
                    WHERE id = OLD.cargo_id;
                END;

                CREATE TRIGGER IF NOT EXISTS trg_ocupantes_update AFTER UPDATE ON Ocupantes
                BEGIN
                    UPDATE Cargos
                    SET total_ocupados = (SELECT COUNT(*) FROM Ocupantes WHERE cargo_id = NEW.cargo_id)
                    WHERE id = NEW.cargo_id;
                    UPDATE Cargos
                    SET total_ocupados = (SELECT COUNT(*) FROM Ocupantes WHERE cargo_id = OLD.cargo_id)
                    WHERE id = OLD.cargo_id;
                END;

                -- Inicializa total_ocupados para 0 em todos os cargos comissionados, 
                -- já que a tabela Ocupantes está começando vazia.
                UPDATE Cargos
                SET total_ocupados = 0
                WHERE tipo_provimento IN ('Comissão', 'Comissao');
            """)
            con.commit()
            print("[MIGRAÇÃO] Tabela Ocupantes e triggers criadas com sucesso.")
    except Exception as e:
        print(f"[ERRO MIGRAÇÃO] Falha ao rodar migrações: {e}")
    finally:
        con.close()

executar_migracao()

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
    """Retorna um cargo com suas leis, fontes e ocupantes."""
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

        ocupantes = con.execute(
            "SELECT * FROM Ocupantes WHERE cargo_id = ? ORDER BY nome",
            (cargo_id,)
        ).fetchall()

        return jsonify({
            "cargo":  dict(cargo),
            "leis":   [dict(l) for l in leis],
            "fontes": [dict(f) for f in fontes],
            "ocupantes": [dict(o) for o in ocupantes],
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
        # Pega a lei antiga para comparar e reverter o impacto no cargo
        lei_antiga = con.execute("SELECT acao, quantidade FROM LeisPertinentes WHERE id=? AND cargo_id=?", (lei_id, cargo_id)).fetchone()
        if not lei_antiga:
            abort(404, description="Lei não encontrada")

        acao_antiga = lei_antiga["acao"]
        qtd_antiga = lei_antiga["quantidade"]

        # Só altera as vagas se houve mudança real de acao ou de quantidade
        alterou_quantitativo = (acao != acao_antiga) or (quantidade != qtd_antiga)

        if alterou_quantitativo:
            cargo = con.execute("SELECT id, total_previstos, total_ocupados FROM Cargos WHERE id=?", (cargo_id,)).fetchone()
            
            # Desfaz o impacto da lei antiga
            prev_atual = cargo["total_previstos"]
            qtd_antiga_val = qtd_antiga or 0
            
            if acao_antiga == "Cria":
                prev_atual = max(0, prev_atual - qtd_antiga_val)
            elif acao_antiga == "Extingue":
                prev_atual = prev_atual + qtd_antiga_val
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
        
        ocupantes = con.execute("SELECT * FROM Ocupantes WHERE cargo_id = ? ORDER BY nome", (cargo_id,)).fetchall()
    finally:
        con.close()

    import io
    try:
        pdf_bytes = gerar_relatorio(dict(cargo), [dict(l) for l in leis], [dict(f) for f in fontes], [dict(o) for o in ocupantes])
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

@app.route("/api/relatorios/estatisticas", methods=["GET"])
def relatorios_estatisticas():
    con = get_db_connection()
    try:
        # KPIs gerais
        res_stats = con.execute("""
            SELECT
              COUNT(*)                                           AS total_cargos,
              COALESCE(SUM(total_previstos), 0)                 AS total_previstos,
              COALESCE(SUM(total_ocupados), 0)                  AS total_ocupados,
              COALESCE(SUM(saldo_vagas), 0)                     AS total_saldo,
              SUM(CASE WHEN saldo_vagas < 0 THEN 1 ELSE 0 END)  AS alertas
            FROM vw_SaldoVagas
        """).fetchone()
        
        stats = dict(res_stats)
        
        # Estatísticas de provimento
        res_prov = con.execute("""
            SELECT
              tipo_provimento                                    AS tipo,
              COUNT(*)                                           AS qtd_cargos,
              COALESCE(SUM(total_previstos), 0)                 AS total_previstos,
              COALESCE(SUM(total_ocupados), 0)                  AS total_ocupados
            FROM vw_SaldoVagas
            GROUP BY tipo_provimento
            ORDER BY tipo_provimento
        """).fetchall()
        
        prov_stats = [dict(r) for r in res_prov]
        
        # Cargos críticos (saldo negativo ou zerado)
        res_criticos = con.execute("""
            SELECT * FROM vw_SaldoVagas
            WHERE saldo_vagas <= 0
            ORDER BY saldo_vagas ASC, nome COLLATE NOCASE
        """).fetchall()
        
        cargos_criticos = [dict(r) for r in res_criticos]
        
        return jsonify({
            "stats": stats,
            "prov_stats": prov_stats,
            "cargos_criticos": cargos_criticos
        })
    finally:
        con.close()

@app.route("/api/relatorios/consolidado", methods=["GET"])
def relatorios_consolidado():
    situacao_delib = request.args.get("situacao_delib")
    situacao = request.args.get("situacao")
    tipo_provimento = request.args.get("tipo_provimento")
    
    where_clauses = []
    params = []
    
    if situacao_delib and situacao_delib.lower() != "todos":
        val = situacao_delib
        if val.lower() == "salvo":
            val = "salvo - em revisão"
        elif val.lower() in ("não enviado", "nao enviado"):
            val = "não enviado"
        elif val.lower() == "enviado":
            val = "Enviado"
        where_clauses.append("situacao_delib = ?")
        params.append(val)
        
    if situacao and situacao.lower() != "todos":
        val = situacao
        if val.lower() == "em vigor":
            val = "Em vigor"
        elif val.lower() == "extinto":
            val = "Extinto"
        elif val.lower() == "revogado":
            val = "Revogado"
        where_clauses.append("situacao = ?")
        params.append(val)
        
    if tipo_provimento and tipo_provimento.lower() != "todos":
        val = tipo_provimento
        if val.lower() == "efetivo":
            val = "Efetivo"
        elif val.lower() in ("comissão", "comissao"):
            val = "Comissão"
        elif val.lower() == "eletivo":
            val = "Eletivo"
        where_clauses.append("tipo_provimento = ?")
        params.append(val)
        
    where_str = ""
    if where_clauses:
        where_str = " WHERE " + " AND ".join(where_clauses)

    con = get_db_connection()
    try:
        # KPIs gerais
        query_stats = f"""
            SELECT
              COUNT(*)                                           AS total_cargos,
              COALESCE(SUM(total_previstos), 0)                 AS total_previstos,
              COALESCE(SUM(total_ocupados), 0)                  AS total_ocupados,
              COALESCE(SUM(saldo_vagas), 0)                     AS total_saldo,
              COALESCE(SUM(CASE WHEN saldo_vagas < 0 THEN 1 ELSE 0 END), 0)  AS alertas
            FROM vw_SaldoVagas
            {where_str}
        """
        res_stats = con.execute(query_stats, params).fetchone()
        stats = dict(res_stats)
        
        # Estatísticas de provimento
        query_prov = f"""
            SELECT
              tipo_provimento                                    AS tipo,
              COUNT(*)                                           AS qtd_cargos,
              COALESCE(SUM(total_previstos), 0)                 AS total_previstos,
              COALESCE(SUM(total_ocupados), 0)                  AS total_ocupados
            FROM vw_SaldoVagas
            {where_str}
            GROUP BY tipo_provimento
            ORDER BY tipo_provimento
        """
        res_prov = con.execute(query_prov, params).fetchall()
        prov_stats = [dict(r) for r in res_prov]
        
        # Todos os cargos ordenados alfabeticamente para a listagem
        query_cargos = f"SELECT * FROM vw_SaldoVagas {where_str} ORDER BY nome COLLATE NOCASE"
        res_cargos = con.execute(query_cargos, params).fetchall()
        cargos = [dict(r) for r in res_cargos]
    finally:
        con.close()
        
    import io
    try:
        pdf_bytes = gerar_relatorio_consolidado(stats, prov_stats, cargos)
    except Exception as e:
        abort(500, description=f"Erro ao gerar PDF Consolidado: {e}")
        
    filename = f"Relatorio_Consolidado_FOPAG_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


@app.route("/api/leis/historico", methods=["GET"])
def leis_historico():
    con = get_db_connection()
    try:
        res = con.execute("""
            SELECT lp.*, c.nome AS cargo_nome, c.codigo_fopag AS cargo_codigo_fopag
            FROM LeisPertinentes lp
            JOIN Cargos c ON lp.cargo_id = c.id
            ORDER BY lp.ano DESC, CAST(lp.numero AS INTEGER) DESC, lp.criado_em DESC
        """).fetchall()
        return jsonify([dict(r) for r in res])
    except Exception as e:
        abort(500, description=f"Erro ao buscar histórico de leis: {e}")
    finally:
        con.close()


@app.route("/api/backup", methods=["GET"])
def fazer_backup():
    """Baixa o banco de dados inteiro como backup."""
    import shutil
    from datetime import datetime
    
    backup_filename = f"Backup_FOPAG_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    
    # É mais seguro copiar o arquivo para um temporário antes de enviar, caso esteja em uso
    import tempfile
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, backup_filename)
    
    shutil.copy2(DB_PATH, temp_path)
    
    return send_file(
        temp_path,
        as_attachment=True,
        download_name=backup_filename
    )


# ── Rotas de Ocupantes ─────────────────────────────────────────────────────────

@app.route("/api/ocupantes", methods=["GET"])
def listar_ocupantes():
    """Lista todos os ocupantes cadastrados com informações do cargo."""
    q = request.args.get("q")
    
    sql = """
        SELECT o.*, c.nome AS cargo_nome, c.codigo_fopag AS cargo_codigo_fopag, c.simbolo_vencimento AS cargo_simbolo_vencimento
        FROM Ocupantes o
        JOIN Cargos c ON o.cargo_id = c.id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (o.nome LIKE ? OR o.matricula LIKE ? OR c.nome LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    
    sql += " ORDER BY o.nome COLLATE NOCASE"
    
    con = get_db_connection()
    try:
        rows = con.execute(sql, params).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        con.close()

@app.route("/api/ocupantes/<int:ocupante_id>", methods=["GET"])
def get_ocupante(ocupante_id):
    """Retorna detalhes de um ocupante."""
    con = get_db_connection()
    try:
        ocupante = con.execute("""
            SELECT o.*, c.nome AS cargo_nome, c.codigo_fopag AS cargo_codigo_fopag
            FROM Ocupantes o
            JOIN Cargos c ON o.cargo_id = c.id
            WHERE o.id = ?
        """, (ocupante_id,)).fetchone()
        if not ocupante:
            abort(404, description="Ocupante não encontrado")
        return jsonify(dict(ocupante))
    finally:
        con.close()

@app.route("/api/ocupantes", methods=["POST"])
def criar_ocupante():
    """Cadastra um novo ocupante."""
    dados = request.get_json()
    cargo_id = dados.get("cargo_id")
    nome = dados.get("nome")
    matricula = dados.get("matricula")
    
    if not cargo_id or not nome or not matricula:
        abort(400, description="cargo_id, nome e matricula são obrigatórios.")
        
    con = get_db_connection()
    try:
        # Valida se o cargo é comissionado
        cargo = con.execute("SELECT tipo_provimento FROM Cargos WHERE id = ?", (cargo_id,)).fetchone()
        if not cargo:
            abort(404, description="Cargo não encontrado")
        if cargo["tipo_provimento"] not in ("Comissão", "Comissao", "Eletivo"):
            abort(400, description="Ocupantes só podem ser cadastrados para cargos comissionados ou eletivos.")

            
        cur = con.execute("""
            INSERT INTO Ocupantes
              (cargo_id, nome, matricula, tipo_recrutamento, simbolo_vencimento,
               portaria, boletim_oficial, data_nomeacao)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            cargo_id, nome, matricula, dados.get("tipo_recrutamento"),
            dados.get("simbolo_vencimento"), dados.get("portaria"),
            dados.get("boletim_oficial"), dados.get("data_nomeacao")
        ))
        con.commit()
        return jsonify({"id": cur.lastrowid, "mensagem": "Ocupante cadastrado com sucesso."}), 201
    finally:
        con.close()

@app.route("/api/ocupantes/<int:ocupante_id>", methods=["PUT"])
def atualizar_ocupante(ocupante_id):
    """Atualiza dados do ocupante."""
    dados = request.get_json()
    cargo_id = dados.get("cargo_id")
    nome = dados.get("nome")
    matricula = dados.get("matricula")
    
    if not cargo_id or not nome or not matricula:
        abort(400, description="cargo_id, nome e matricula são obrigatórios.")
        
    con = get_db_connection()
    try:
        ocupante = con.execute("SELECT id FROM Ocupantes WHERE id = ?", (ocupante_id,)).fetchone()
        if not ocupante:
            abort(404, description="Ocupante não encontrado")
            
        cargo = con.execute("SELECT tipo_provimento FROM Cargos WHERE id = ?", (cargo_id,)).fetchone()
        if not cargo:
            abort(404, description="Cargo não encontrado")
        if cargo["tipo_provimento"] not in ("Comissão", "Comissao", "Eletivo"):
            abort(400, description="Ocupantes só podem ser cadastrados para cargos comissionados ou eletivos.")

            
        con.execute("""
            UPDATE Ocupantes SET
              cargo_id=?, nome=?, matricula=?, tipo_recrutamento=?,
              simbolo_vencimento=?, portaria=?, boletim_oficial=?, data_nomeacao=?,
              atualizado_em=datetime('now','localtime')
            WHERE id=?
        """, (
            cargo_id, nome, matricula, dados.get("tipo_recrutamento"),
            dados.get("simbolo_vencimento"), dados.get("portaria"),
            dados.get("boletim_oficial"), dados.get("data_nomeacao"),
            ocupante_id
        ))
        con.commit()
        return jsonify({"mensagem": "Ocupante atualizado com sucesso."})
    finally:
        con.close()

@app.route("/api/ocupantes/<int:ocupante_id>", methods=["DELETE"])
def deletar_ocupante(ocupante_id):
    """Exonera (remove) um ocupante."""
    con = get_db_connection()
    try:
        ocupante = con.execute("SELECT id, cargo_id FROM Ocupantes WHERE id = ?", (ocupante_id,)).fetchone()
        if not ocupante:
            abort(404, description="Ocupante não encontrado")
            
        con.execute("DELETE FROM Ocupantes WHERE id = ?", (ocupante_id,))
        con.commit()
        return jsonify({"mensagem": "Ocupante exonerado/excluído com sucesso."})
    finally:
        con.close()

@app.route("/api/cargos/<int:cargo_id>/ocupantes", methods=["GET"])
def listar_ocupantes_cargo(cargo_id):
    """Lista ocupantes de um cargo específico."""
    con = get_db_connection()
    try:
        rows = con.execute("""
            SELECT * FROM Ocupantes
            WHERE cargo_id = ?
            ORDER BY nome COLLATE NOCASE
        """, (cargo_id,)).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        con.close()


@app.route("/")
def index():
    with open(HTML_DIR / "index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return html_content

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
