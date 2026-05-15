"""
FOPAG — Sistema de Gestão de Cargos e Vagas
Prefeitura Municipal de Miracema
Backend: FastAPI + SQLite

Uso:  python app.py
      (ou duplo clique em iniciar.bat)

Acesso: http://localhost:8000
"""

import sqlite3, re, os, webbrowser, threading, traceback
from pathlib import Path
from typing import Optional, List
from contextlib import contextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

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

# ── Banco ──────────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

# ── Schemas Pydantic ───────────────────────────────────────────────────────────
class CargoCreate(BaseModel):
    nome:               str
    codigo_fopag:       Optional[str] = None
    situacao:           str = "Em vigor"
    situacao_delib:     str = "não enviado"
    tipo_provimento:    str = "Efetivo"
    # Aceita tanto "Comissão" quanto "Comissao" para compatibilidade

    escolaridade:       Optional[str] = None
    carga_horaria:      Optional[str] = None
    simbolo_vencimento: Optional[str] = None
    total_previstos:    int = 0
    total_ocupados:     int = 0
    atribuicoes:        Optional[str] = None

class LeiCreate(BaseModel):
    numero:     str
    ano:        int
    acao:       str
    quantidade: Optional[int] = None
    descricao:  Optional[str] = None

class OcupadosUpdate(BaseModel):
    total_ocupados: int

# ── Verificação de integridade do banco ───────────────────────────────────────
def verificar_banco():
    """Verifica se o banco tem a view necessária; lança erro descritivo se não."""
    try:
        with get_db() as con:
            views = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            ).fetchall()]
            if 'vw_SaldoVagas' not in views:
                raise SystemExit(
                    "[ERRO] O banco está incompleto (falta a view vw_SaldoVagas).\n"
                    "Execute: python criar_banco.py  para recriar o banco."
                )
            count = con.execute("SELECT COUNT(*) FROM Cargos").fetchone()[0]
            print(f"  Banco OK: {count} cargos encontrados.")
    except SystemExit:
        raise
    except Exception as e:
        raise SystemExit(f"[ERRO] Falha ao abrir o banco de dados:\n  {e}\n"
                         "Execute: python criar_banco.py")

verificar_banco()

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="FOPAG", version="1.0")

# Adaptador para o PythonAnywhere (que usa WSGI)
from a2wsgi import ASGIMiddleware
wsgi_app = ASGIMiddleware(app)

# Handler global de exceções — evita 500 sem informação
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"[ERRO] {request.url}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "tipo": type(exc).__name__}
    )

# ── Rotas de dados ─────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    """KPIs do painel principal."""
    with get_db() as con:
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
        return dict(r)

@app.get("/api/cargos")
async def listar_cargos(
    situacao: Optional[str] = None,
    tipo:     Optional[str] = None,
    q:        Optional[str] = None,
):
    """Lista todos os cargos com saldo calculado. Suporta filtros por situação, tipo e busca."""
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
    with get_db() as con:
        rows = con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

@app.get("/api/cargos/{cargo_id}")
async def get_cargo(cargo_id: int):
    """Retorna um cargo com suas leis e fontes de carga horária."""
    with get_db() as con:
        cargo = con.execute(
            "SELECT * FROM vw_SaldoVagas WHERE id = ?", (cargo_id,)
        ).fetchone()
        if not cargo:
            raise HTTPException(404, "Cargo não encontrado")

        leis = con.execute(
            "SELECT * FROM LeisPertinentes WHERE cargo_id = ? ORDER BY ano, numero",
            (cargo_id,)
        ).fetchall()

        fontes = con.execute(
            "SELECT * FROM FontesCargaHoraria WHERE cargo_id = ?",
            (cargo_id,)
        ).fetchall()

        return {
            "cargo":  dict(cargo),
            "leis":   [dict(l) for l in leis],
            "fontes": [dict(f) for f in fontes],
        }

@app.post("/api/cargos", status_code=201)
async def criar_cargo(dados: CargoCreate):
    """Cria um novo cargo no quadro."""
    with get_db() as con:
        cur = con.execute("""
            INSERT INTO Cargos
              (nome, codigo_fopag, situacao, situacao_delib, tipo_provimento, escolaridade,
               carga_horaria, simbolo_vencimento, total_previstos, total_ocupados, atribuicoes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (dados.nome, dados.codigo_fopag, dados.situacao, dados.situacao_delib, dados.tipo_provimento,
              dados.escolaridade, dados.carga_horaria, dados.simbolo_vencimento,
              dados.total_previstos, dados.total_ocupados, dados.atribuicoes))
        return {"id": cur.lastrowid, "mensagem": "Cargo criado com sucesso."}

@app.put("/api/cargos/{cargo_id}")
async def atualizar_cargo(cargo_id: int, dados: CargoCreate):
    """Atualiza os dados de um cargo existente."""
    with get_db() as con:
        cargo = con.execute("SELECT id FROM Cargos WHERE id=?", (cargo_id,)).fetchone()
        if not cargo:
            raise HTTPException(404, "Cargo não encontrado")
        con.execute("""
            UPDATE Cargos SET
              nome=?, codigo_fopag=?, situacao=?, situacao_delib=?, tipo_provimento=?, escolaridade=?,
              carga_horaria=?, simbolo_vencimento=?, total_previstos=?,
              total_ocupados=?, atribuicoes=?
            WHERE id=?
        """, (dados.nome, dados.codigo_fopag, dados.situacao, dados.situacao_delib, dados.tipo_provimento,
              dados.escolaridade, dados.carga_horaria, dados.simbolo_vencimento,
              dados.total_previstos, dados.total_ocupados, dados.atribuicoes, cargo_id))
        return {"mensagem": "Cargo atualizado."}

@app.patch("/api/cargos/{cargo_id}/ocupados")
async def atualizar_ocupados(cargo_id: int, dados: OcupadosUpdate):
    """Atualiza somente o total de vagas ocupadas."""
    with get_db() as con:
        cargo = con.execute(
            "SELECT total_previstos FROM Cargos WHERE id=?", (cargo_id,)
        ).fetchone()
        if not cargo:
            raise HTTPException(404, "Cargo não encontrado")
        con.execute(
            "UPDATE Cargos SET total_ocupados=? WHERE id=?",
            (max(0, dados.total_ocupados), cargo_id)
        )
        saldo = cargo["total_previstos"] - max(0, dados.total_ocupados)
        return {"saldo_novo": saldo}

@app.post("/api/cargos/{cargo_id}/leis", status_code=201)
async def registrar_lei(cargo_id: int, lei: LeiCreate):
    """
    Registra uma lei pertinente e aplica seu impacto sobre total_previstos.
    Motor de saldo: Cria → incrementa | Extingue → decrementa | Fixa → valor absoluto
    """
    ACOES_COM_QTD = {"Cria", "Extingue", "Fixa"}
    ACOES_VALIDAS = {"Cria", "Extingue", "Fixa", "Altera", "Regulamenta", "Outro"}

    if lei.acao not in ACOES_VALIDAS:
        raise HTTPException(400, f"Ação inválida: {lei.acao}")
    if lei.acao in ACOES_COM_QTD and lei.quantidade is None:
        raise HTTPException(400, f"Ação '{lei.acao}' exige o campo 'quantidade'.")

    with get_db() as con:
        cargo = con.execute(
            "SELECT id, nome, total_previstos, total_ocupados FROM Cargos WHERE id=?",
            (cargo_id,)
        ).fetchone()
        if not cargo:
            raise HTTPException(404, "Cargo não encontrado")

        prev_antes = cargo["total_previstos"]

        # Calcula novo total_previstos
        if lei.acao == "Cria":
            novo_prev = prev_antes + lei.quantidade
        elif lei.acao == "Extingue":
            novo_prev = max(0, prev_antes - lei.quantidade)
        elif lei.acao == "Fixa":
            novo_prev = lei.quantidade
        else:
            novo_prev = prev_antes  # ações qualitativas não alteram o número

        # Atualiza cargo
        if novo_prev != prev_antes:
            con.execute(
                "UPDATE Cargos SET total_previstos=? WHERE id=?",
                (novo_prev, cargo_id)
            )

        # Registra histórico
        cur = con.execute("""
            INSERT INTO LeisPertinentes
              (cargo_id, numero, ano, descricao, acao, quantidade)
            VALUES (?,?,?,?,?,?)
        """, (cargo_id, lei.numero, lei.ano, lei.descricao, lei.acao,
              lei.quantidade if lei.acao in ACOES_COM_QTD else None))

        saldo_novo = novo_prev - cargo["total_ocupados"]
        return {
            "lei_id":          cur.lastrowid,
            "saldo_anterior":  prev_antes - cargo["total_ocupados"],
            "saldo_novo":      saldo_novo,
            "total_previstos": novo_prev,
            "mensagem":        f"Lei {lei.numero}/{lei.ano} registrada. Saldo: {saldo_novo:+d}",
        }

@app.get("/api/cargos/{cargo_id}/leis")
async def listar_leis(cargo_id: int):
    with get_db() as con:
        leis = con.execute(
            "SELECT * FROM LeisPertinentes WHERE cargo_id=? ORDER BY ano, CAST(numero AS INTEGER)",
            (cargo_id,)
        ).fetchall()
        return [dict(l) for l in leis]


@app.get("/api/cargos/{cargo_id}/relatorio")
async def baixar_relatorio(cargo_id: int):
    """Gera e retorna o relatório PDF do cargo no padrão A4."""
    with get_db() as con:
        cargo = con.execute(
            "SELECT * FROM vw_SaldoVagas WHERE id = ?", (cargo_id,)
        ).fetchone()
        if not cargo:
            raise HTTPException(404, "Cargo não encontrado")

        leis = con.execute(
            "SELECT * FROM LeisPertinentes WHERE cargo_id = ? ORDER BY ano, CAST(numero AS INTEGER)",
            (cargo_id,)
        ).fetchall()

        fontes = con.execute(
            "SELECT * FROM FontesCargaHoraria WHERE cargo_id = ?",
            (cargo_id,)
        ).fetchall()

    try:
        pdf_bytes = gerar_relatorio(dict(cargo), [dict(l) for l in leis], [dict(f) for f in fontes])
    except Exception as e:
        raise HTTPException(500, f"Erro ao gerar PDF: {e}")

    safe_name = re.sub(r'[^\w\s-]', '', dict(cargo)['nome']).strip().replace(' ', '_')
    filename = f"Relatorio_FOPAG_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

# ── Servir frontend ────────────────────────────────────────────────────────────
HTML_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=HTML_DIR), name="static")

from fastapi.responses import HTMLResponse

@app.get("/")
async def index():
    with open(HTML_DIR / "index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# ── Entrada ────────────────────────────────────────────────────────────────────
def abrir_navegador():
    import time; time.sleep(1.2)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 50)
    print("  FOPAG — Sistema de Gestão de Cargos")
    print("  Prefeitura de Miracema")
    print("=" * 50)
    print(f"  Banco: {DB_PATH.name}")
    print("  Abrindo navegador em http://localhost:8000")
    print("  (Ctrl+C para encerrar)")
    print("=" * 50)
    threading.Thread(target=abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
