"""
FOPAG - setup.py
Chamado pelo iniciar.bat antes de subir o servidor.
Verifica se o banco esta valido; se nao, recria do zero.
Grava erros em erro_log.txt para diagnostico.
"""
import sqlite3, sys, os, traceback, shutil
from pathlib import Path

BASE_DIR  = Path(__file__).parent
DATA_DIR  = Path(os.environ.get("DATA_DIR", BASE_DIR))
DB_PATH   = DATA_DIR / "quadro_pessoal.db"
XLSX_PATH = BASE_DIR / "CARGOS EFETIVOS E COMISSIONADOS - PMM - Ativos e extintos - 2026.xlsx"
LOG_PATH  = BASE_DIR / "erro_log.txt"

def log_erro(msg):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(msg)
    print(msg)

def banco_valido():
    """Retorna True se o banco existe e tem a view e pelo menos 1 cargo."""
    if not DB_PATH.exists():
        return False
    try:
        # Lê os primeiros 16 bytes para verificar assinatura SQLite
        with open(DB_PATH, "rb") as f:
            header = f.read(16)
        if not header.startswith(b"SQLite format 3"):
            print("  Banco corrompido (cabecalho invalido). Recriando...")
            DB_PATH.unlink()
            return False
        con = sqlite3.connect(DB_PATH)
        views = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"
        ).fetchall()]
        ok = "vw_SaldoVagas" in views
        count = con.execute("SELECT COUNT(*) FROM Cargos").fetchone()[0] if ok else 0
        con.close()
        if not ok or count == 0:
            print("  Banco incompleto. Recriando...")
            DB_PATH.unlink()
            return False
        print(f"  Banco OK: {count} cargos.")
        return True
    except Exception as e:
        print(f"  Banco com erro ({e}). Recriando...")
        try: DB_PATH.unlink()
        except: pass
        return False

def criar_banco():
    """Cria o banco do zero e importa a planilha."""
    try:
        import pandas as pd
        import re
    except ImportError as e:
        log_erro(f"Dependencia faltando: {e}\nExecute:  pip install pandas openpyxl")
        return False

    if not XLSX_PATH.exists():
        log_erro(
            f"Planilha nao encontrada:\n{XLSX_PATH}\n\n"
            "Certifique-se de que a planilha esta na mesma pasta do iniciar.bat."
        )
        return False

    SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS Cargos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    codigo_fopag TEXT,
    situacao TEXT NOT NULL DEFAULT 'Em vigor'
        CHECK (situacao IN ('Em vigor','Extinto','Revogado')),
    situacao_delib TEXT NOT NULL DEFAULT 'não enviado'
        CHECK (situacao_delib IN ('Enviado','salvo - em revisão','não enviado')),
    tipo_provimento TEXT NOT NULL
        CHECK (tipo_provimento IN ('Efetivo','Comissao','Eletivo','Comissão')),
    escolaridade TEXT, carga_horaria TEXT, simbolo_vencimento TEXT,
    total_previstos INTEGER NOT NULL DEFAULT 0 CHECK (total_previstos >= 0),
    total_ocupados  INTEGER NOT NULL DEFAULT 0 CHECK (total_ocupados  >= 0),
    atribuicoes TEXT,
    recrutamento TEXT,
    restricao_exigencia TEXT,
    fonte_carga_horaria TEXT,
    fonte_atribuicoes   TEXT,
    criado_em   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS FontesCargaHoraria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id INTEGER NOT NULL REFERENCES Cargos(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL, numero TEXT, ano INTEGER, detalhes TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS LeisPertinentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id INTEGER NOT NULL REFERENCES Cargos(id) ON DELETE CASCADE,
    numero TEXT NOT NULL, ano INTEGER, descricao TEXT,
    acao TEXT NOT NULL DEFAULT 'Outro',
    quantidade INTEGER DEFAULT NULL, texto_original TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE VIEW IF NOT EXISTS vw_SaldoVagas AS
SELECT id, nome, codigo_fopag, situacao, situacao_delib, tipo_provimento,
       escolaridade, carga_horaria, simbolo_vencimento,
       total_previstos, total_ocupados,
       (total_previstos - total_ocupados) AS saldo_vagas,
       CASE WHEN (total_previstos - total_ocupados) < 0 THEN 1 ELSE 0 END AS alerta_saldo_negativo,
       atribuicoes, criado_em, atualizado_em,
       recrutamento, restricao_exigencia, fonte_carga_horaria, fonte_atribuicoes
FROM Cargos;

CREATE TABLE IF NOT EXISTS Ocupantes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id                INTEGER NOT NULL REFERENCES Cargos (id) ON DELETE CASCADE,
    nome                    TEXT    NOT NULL,
    matricula               TEXT    NOT NULL,
    tipo_recrutamento       TEXT    CHECK (tipo_recrutamento IN ('Amplo', 'Limitado', 'Outro', NULL)),
    simbolo_vencimento      TEXT    CHECK (simbolo_vencimento IN ('SS', 'SP', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5', 'CC6', 'FGDE 1', 'FGDE 2', 'FGDE 3', 'FGDE 4', 'FGDE 5', 'FGDE 6', NULL)),
    portaria                TEXT,
    boletim_oficial         TEXT,
    data_nomeacao           TEXT,
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

CREATE TABLE IF NOT EXISTS HistoricoExoneracoes (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                    TEXT    NOT NULL,
    matricula               TEXT    NOT NULL,
    cargo_id                INTEGER REFERENCES Cargos (id) ON DELETE SET NULL,
    cargo_nome              TEXT    NOT NULL,
    secretaria              TEXT,
    portaria_nomeacao       TEXT,
    data_nomeacao           TEXT,
    data_exoneracao         TEXT    NOT NULL,  -- YYYY-MM-DD
    portaria_exoneracao     TEXT    NOT NULL,
    boletim_exoneracao      TEXT    NOT NULL,
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
"""

    COLUNAS_PRINCIPAIS = {
        'Cargo','Situacao','Situação','Código FOPAG','Tipo de Provimento',
        'Recrutamento','Restricao - Exigencia','Restrição - Exigência',
        'Carga Horaria Semanal','Carga Horária Semanal',
        'Fonte Carga Horaria','Fonte Carga Horária',
        'Simbolo de Vencimento','Símbolo de Vencimento',
        'Total de cargos PREVISTOS','Total de cargos OCUPADOS',
        'SALDO TOTAL','Atribuicoes','Atribuições','Coluna1',
    }

    def _str(v):
        if pd.isna(v): return None
        s = str(v).strip()
        return None if s in ('', 'nan', 'NaN', 'None') else s

    def _int(v, d=0):
        try: return int(float(str(v))) if not pd.isna(v) else d
        except: return d

    def _sit(v):
        if pd.isna(v): return 'Em vigor'
        return {'Em vigor':'Em vigor','Extinto':'Extinto','Extintos':'Extinto',
                'Revogado':'Revogado'}.get(str(v).strip(), 'Em vigor')

    def _tipo(v):
        if pd.isna(v): return 'Efetivo'
        m = {'Efetivo':'Efetivo','Comissão':'Comissão','Comissao':'Comissão',
             'Eletivo':'Eletivo'}.get(str(v).strip())
        return m if m else 'Efetivo'

    def _ch(v):
        if pd.isna(v): return None
        s = str(v).strip()
        m = re.search(r'\b(\d+)\b', s)
        if m and m.group(1) in {'10','20','24','25','30','40','44'}: return m.group(1)
        return s if s else None

    def _lei_parse(txt):
        if not isinstance(txt, str) or not txt.strip():
            return {'acao': 'Outro', 'quantidade': None}
        t = txt.strip()
        for pat, acao in [(r'^Cria\s+\+?(\d+)','Cria'),
                          (r'^Extingue\s+(\d+)','Extingue'),
                          (r'^Fixa\s+(?:em\s+)?(\d+)','Fixa')]:
            m = re.match(pat, t, re.I)
            if m: return {'acao': acao, 'quantidade': int(m.group(1))}
        m = re.search(r'Totaliza\s+(\d+)', t, re.I)
        if m: return {'acao': 'Fixa', 'quantidade': int(m.group(1))}
        m = re.match(r'^Aumenta\s+para\s+(\d+)', t, re.I)
        if m: return {'acao': 'Fixa', 'quantidade': int(m.group(1))}
        if re.match(r'^Altera', t, re.I): return {'acao': 'Altera', 'quantidade': None}
        if re.match(r'^(Regulamenta|Plano\s+de)', t, re.I): return {'acao': 'Regulamenta', 'quantidade': None}
        return {'acao': 'Outro', 'quantidade': None}

    def _lei_cab(cab):
        m = re.match(r'^[\w\s\.]*?(\d[\d\.]*)/([\d]{2,4})', cab.strip())
        if m:
            num = m.group(1).replace('.', '')
            ano = int(m.group(2))
            if len(m.group(2)) == 2:
                ano = 1900 + ano if ano >= 90 else 2000 + ano
            return num, ano
        return cab[:50], None

    try:
        print("  Lendo planilha...")
        temp_xlsx = str(XLSX_PATH) + ".tmp.xlsx"
        shutil.copy2(str(XLSX_PATH), temp_xlsx)
        try:
            df = pd.read_excel(temp_xlsx, sheet_name='Planilha1', dtype=str)
        finally:
            os.remove(temp_xlsx)
            
        df = df[df['Cargo'].notna() & (df['Cargo'].str.strip() != '')].reset_index(drop=True)
        cols_lei = [c for c in df.columns if c not in COLUNAS_PRINCIPAIS]
        print(f"  {len(df)} cargos | {len(cols_lei)} colunas de leis")

        print("  Criando banco...")
        con = sqlite3.connect(str(DB_PATH))
        con.executescript(SCHEMA)
        con.commit()

        print("  Importando dados...")
        n_cargos = n_leis = n_erros = 0

        for idx, row in df.iterrows():
            try:
                cur = con.execute(
                    "INSERT INTO Cargos (nome,codigo_fopag,situacao,situacao_delib,tipo_provimento,"
                    "escolaridade,carga_horaria,simbolo_vencimento,total_previstos,total_ocupados,atribuicoes)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (_str(row.get('Cargo')) or '(sem nome)',
                     _str(row.get('Código FOPAG')),
                     _sit(row.get('Situação')),
                     'não enviado',
                     _tipo(row.get('Tipo de Provimento')),
                     _str(row.get('Restrição - Exigência')),
                     _ch(row.get('Carga Horária Semanal')),
                     _str(row.get('Símbolo de Vencimento')),
                     _int(row.get('Total de cargos PREVISTOS'), 0),
                     _int(row.get('Total de cargos OCUPADOS'), 0),
                     _str(row.get('Atribuições')))
                )
                cid = cur.lastrowid
                n_cargos += 1

                for col in cols_lei:
                    val = row.get(col)
                    if pd.isna(val) or str(val).strip() in ('','nan'): continue
                    txt = str(val).strip()
                    num, ano = _lei_cab(col)
                    p = _lei_parse(txt)
                    con.execute(
                        "INSERT INTO LeisPertinentes "
                        "(cargo_id,numero,ano,descricao,acao,quantidade,texto_original)"
                        " VALUES (?,?,?,?,?,?,?)",
                        (cid, num, ano, txt[:500], p['acao'],
                         p['quantidade'] if p['acao'] in ('Cria','Extingue','Fixa') else None,
                         txt[:500])
                    )
                    n_leis += 1

            except Exception:
                n_erros += 1

        con.commit()

        # Verifica resultado
        r = con.execute(
            "SELECT COUNT(*), SUM(saldo_vagas) FROM vw_SaldoVagas"
        ).fetchone()
        con.close()

        print(f"  Importados: {n_cargos} cargos, {n_leis} leis ({n_erros} avisos)")
        print(f"  Verificacao: {r[0]} cargos no banco, saldo geral: {r[1]}")
        return True

    except Exception as e:
        log_erro(f"ERRO ao criar banco:\n{traceback.format_exc()}")
        try: DB_PATH.unlink()
        except: pass
        return False

# ── main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if banco_valido():
        print("  Banco pronto.")
        sys.exit(0)
    else:
        print("  Criando banco do zero...")
        ok = criar_banco()
        sys.exit(0 if ok else 1)
