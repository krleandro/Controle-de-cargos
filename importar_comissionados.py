import pandas as pd
import sqlite3
import unicodedata
import re
from pathlib import Path

XLSX_PATH = Path("CARGOS EM COMISSÃO 2026 atualizado.xlsx")
DB_PATH = Path("quadro_pessoal.db")

def normalize_name(s):
    if not s: return ""
    s = str(s).strip().upper()
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
    s = re.sub(r'[^A-Z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def normalize_symbol(s):
    if not s or pd.isna(s): return None
    s = str(s).strip().upper()
    if 'SS' in s: return 'SS'
    if 'SP' in s: return 'SP'
    
    # CC-1, CC-2... -> CC1, CC2...
    m = re.match(r'CC\s*-\s*(\d)', s)
    if m:
        return f"CC{m.group(1)}"
    if s in ('CC1', 'CC2', 'CC3', 'CC4', 'CC5', 'CC6'):
        return s
        
    # FG - 1,00, FG - 0,60... -> FGDE 1, FGDE 2...
    if 'FG' in s:
        m = re.search(r'0[.,](\d+)', s)
        if m:
            val = int(m.group(1))
            if val == 80: return 'FGDE 2'
            if val == 70: return 'FGDE 3'
            if val == 60: return 'FGDE 4'
            if val in (50, 51): return 'FGDE 5'
            if val in (40, 10): return 'FGDE 6'
        if '1,00' in s or '1.00' in s:
            return 'FGDE 1'
            
    valid = {'SS', 'SP', 'CC1', 'CC2', 'CC3', 'CC4', 'CC5', 'CC6', 'FGDE 1', 'FGDE 2', 'FGDE 3', 'FGDE 4', 'FGDE 5', 'FGDE 6'}
    if s in valid:
        return s
    return None

def normalize_recrutamento(r):
    if not r or pd.isna(r): return None
    r = str(r).strip().upper()
    if r == 'AMPLO': return 'Amplo'
    if r == 'LIMITADO': return 'Limitado'
    return 'Outro'

def clean_matricula(m):
    if not m or pd.isna(m): return ""
    try:
        # Convert float to int, then to string
        return str(int(float(str(m).strip())))
    except:
        return str(m).strip()

def clean_str(val):
    if not val or pd.isna(val): return None
    s = str(val).strip()
    return None if s in ('', 'nan', 'NaN', 'None') else s

def clean_int(val, default=1):
    try:
        return int(float(str(val))) if not pd.isna(val) else default
    except:
        return default

# Connect to database
con = sqlite3.connect(DB_PATH)
con.execute("PRAGMA foreign_keys = ON")

# Garante a existência da coluna 'secretaria' na tabela Cargos
cols = [col[1] for col in con.execute("PRAGMA table_info(Cargos)").fetchall()]
if 'secretaria' not in cols:
    print("Adicionando coluna 'secretaria' na tabela Cargos...")
    con.execute("ALTER TABLE Cargos ADD COLUMN secretaria TEXT;")
    con.commit()


# 1. Clear existing occupants
print("Limpando tabela Ocupantes...")
con.execute("DELETE FROM Ocupantes")
con.commit()

# Load all cargos into memory for quick lookup
def load_cargos_map():
    rows = con.execute("SELECT id, nome FROM Cargos").fetchall()
    return {normalize_name(r[1]): r[0] for r in rows}

cargos_map = load_cargos_map()

# Load Excel File
xl = pd.ExcelFile(XLSX_PATH)

total_imported = 0
total_cargos_created = 0

# --- Tab 1: CC ---
print("\nProcessando aba 'CC'...")
df_cc = xl.parse('CC', header=None)
current_secretaria = "GABINETE DO PREFEITO"

for idx, row in df_cc.iloc[2:].iterrows():
    # Detecta cabeçalhos de seção (secretarias)
    if pd.notna(row[0]) and pd.isna(row[1]) and pd.isna(row[2]) and pd.isna(row[3]):
        sec_val = str(row[0]).strip()
        if "QUADRO DE CARGOS" not in sec_val.upper():
            current_secretaria = sec_val
        continue

    nome = clean_str(row[2])
    cargo_name = clean_str(row[3])
    
    if not nome or not cargo_name:
        continue
        
    matricula = clean_matricula(row[0])
    portaria = clean_str(row[1])
    vagas_existentes = clean_int(row[4], 1)
    simbolo_raw = clean_str(row[6])
    recrutamento_raw = clean_str(row[8])
    
    norm_cargo = normalize_name(cargo_name)
    
    # Check if cargo exists
    if norm_cargo in cargos_map:
        cargo_id = cargos_map[norm_cargo]
        tipo_prov = 'Eletivo' if recrutamento_raw == 'ELETIVO' else 'Comissão'
        simbolo_cargo = normalize_symbol(simbolo_raw)
        recrutamento_cargo = normalize_recrutamento(recrutamento_raw)
        if recrutamento_cargo == 'Outro':
            recrutamento_cargo = None
        con.execute("""
            UPDATE Cargos
            SET tipo_provimento = ?,
                simbolo_vencimento = COALESCE(simbolo_vencimento, ?),
                recrutamento = COALESCE(recrutamento, ?),
                total_previstos = ?,
                secretaria = ?
            WHERE id = ?
        """, (tipo_prov, simbolo_cargo, recrutamento_cargo, vagas_existentes, current_secretaria, cargo_id))

    else:
        # Create cargo
        tipo_prov = 'Eletivo' if recrutamento_raw == 'ELETIVO' else 'Comissão'
        simbolo_cargo = normalize_symbol(simbolo_raw)
        recrutamento_cargo = normalize_recrutamento(recrutamento_raw)
        if recrutamento_cargo == 'Outro':
            recrutamento_cargo = None
            
        cur = con.execute("""
            INSERT INTO Cargos
              (nome, situacao, tipo_provimento, simbolo_vencimento, recrutamento, total_previstos, total_ocupados, secretaria)
            VALUES (?, 'Em vigor', ?, ?, ?, ?, 0, ?)
        """, (cargo_name, tipo_prov, simbolo_cargo, recrutamento_cargo, vagas_existentes, current_secretaria))
        cargo_id = cur.lastrowid
        cargos_map[norm_cargo] = cargo_id
        total_cargos_created += 1

        
    # Insert occupant
    con.execute("""
        INSERT INTO Ocupantes
          (cargo_id, nome, matricula, tipo_recrutamento, simbolo_vencimento, portaria, data_nomeacao)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
    """, (
        cargo_id, nome, matricula,
        normalize_recrutamento(recrutamento_raw),
        normalize_symbol(simbolo_raw),
        portaria
    ))
    total_imported += 1

# --- Tab 2: Conselho Tutelar ---
print("\nProcessando aba 'Conselho Tutelar'...")
df_ct = xl.parse('Conselho Tutelar', header=None)
for idx, row in df_ct.iloc[1:].iterrows():
    nome = clean_str(row[2])
    cargo_name = clean_str(row[3])
    
    if not nome or not cargo_name:
        continue
        
    matricula = clean_matricula(row[0])
    portaria = clean_str(row[1])
    vagas_existentes = clean_int(row[4], 5)
    simbolo_raw = clean_str(row[6]) or 'CC-2'
    
    norm_cargo = normalize_name(cargo_name)
    
    # Check if cargo exists
    if norm_cargo in cargos_map:
        cargo_id = cargos_map[norm_cargo]
        simbolo_cargo = normalize_symbol(simbolo_raw)
        con.execute("""
            UPDATE Cargos
            SET tipo_provimento = 'Comissão',
                simbolo_vencimento = COALESCE(simbolo_vencimento, ?),
                recrutamento = 'Amplo',
                total_previstos = ?,
                secretaria = ?
            WHERE id = ?
        """, (simbolo_cargo, vagas_existentes, 'SECRETARIA MUNICIPAL DE PROMOÇÃO E BEM ESTAR SOCIAL', cargo_id))

    else:
        # Create cargo
        simbolo_cargo = normalize_symbol(simbolo_raw)
        cur = con.execute("""
            INSERT INTO Cargos
              (nome, situacao, tipo_provimento, simbolo_vencimento, recrutamento, total_previstos, total_ocupados, secretaria)
            VALUES (?, 'Em vigor', 'Comissão', ?, 'Amplo', ?, 0, ?)
        """, (cargo_name, simbolo_cargo, vagas_existentes, 'SECRETARIA MUNICIPAL DE PROMOÇÃO E BEM ESTAR SOCIAL'))
        cargo_id = cur.lastrowid
        cargos_map[norm_cargo] = cargo_id
        total_cargos_created += 1

        
    # Insert occupant
    con.execute("""
        INSERT INTO Ocupantes
          (cargo_id, nome, matricula, tipo_recrutamento, simbolo_vencimento, portaria, data_nomeacao)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
    """, (
        cargo_id, nome, matricula,
        'Amplo',
        normalize_symbol(simbolo_raw),
        portaria
    ))
    total_imported += 1

# --- Tab 3: Diretores de Escola ---
print("\nProcessando aba 'Diretores de Escola'...")
df_de = xl.parse('Diretores de Escola', header=None)
for idx, row in df_de.iterrows():
    nome = clean_str(row[2])
    cargo_name = clean_str(row[3])
    
    if not nome or not cargo_name:
        continue
        
    matricula = clean_matricula(row[0])
    portaria = clean_str(row[1])
    vagas_existentes = clean_int(row[4], 1)
    simbolo_raw = clean_str(row[6])
    
    norm_cargo = normalize_name(cargo_name)
    
    # Check if cargo exists
    if norm_cargo in cargos_map:
        cargo_id = cargos_map[norm_cargo]
        simbolo_cargo = normalize_symbol(simbolo_raw)
        con.execute("""
            UPDATE Cargos
            SET tipo_provimento = 'Comissão',
                simbolo_vencimento = COALESCE(simbolo_vencimento, ?),
                recrutamento = 'Amplo',
                total_previstos = ?,
                secretaria = ?
            WHERE id = ?
        """, (simbolo_cargo, vagas_existentes, 'SECRETARIA MUNICIPAL DE EDUCAÇÃO', cargo_id))

    else:
        # Create cargo
        simbolo_cargo = normalize_symbol(simbolo_raw)
        cur = con.execute("""
            INSERT INTO Cargos
              (nome, situacao, tipo_provimento, simbolo_vencimento, recrutamento, total_previstos, total_ocupados, secretaria)
            VALUES (?, 'Em vigor', 'Comissão', ?, 'Amplo', ?, 0, ?)
        """, (cargo_name, simbolo_cargo, vagas_existentes, 'SECRETARIA MUNICIPAL DE EDUCAÇÃO'))
        cargo_id = cur.lastrowid
        cargos_map[norm_cargo] = cargo_id
        total_cargos_created += 1

        
    # Insert occupant
    con.execute("""
        INSERT INTO Ocupantes
          (cargo_id, nome, matricula, tipo_recrutamento, simbolo_vencimento, portaria, data_nomeacao)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
    """, (
        cargo_id, nome, matricula,
        'Amplo',
        normalize_symbol(simbolo_raw),
        portaria
    ))
    total_imported += 1

con.commit()
con.close()

print("\n=== IMPORTAÇÃO CONCLUÍDA COM SUCESSO! ===")
print(f"Total de Ocupantes Importados: {total_imported}")
print(f"Novos Cargos Criados no Banco: {total_cargos_created}")
