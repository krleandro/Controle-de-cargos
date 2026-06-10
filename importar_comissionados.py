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
    
    m = re.match(r'CC\s*-\s*(\d)', s)
    if m:
        return f"CC{m.group(1)}"
    if s in ('CC1', 'CC2', 'CC3', 'CC4', 'CC5', 'CC6'):
        return s
        
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

# Reset total_ocupados to 0 for all comissionado/eletivo cargos
print("Resetando contagem de ocupados para cargos comissionados/eletivos...")
con.execute("UPDATE Cargos SET total_ocupados = 0 WHERE tipo_provimento IN ('Comissão', 'Eletivo')")
con.commit()

# Clear existing occupants
print("Limpando tabela Ocupantes...")
con.execute("DELETE FROM Ocupantes")
con.commit()

# Load all cargos into memory for matching
def load_db_cargos():
    rows = con.execute("SELECT id, nome, secretaria, tipo_provimento FROM Cargos").fetchall()
    return [{
        'id': r[0],
        'nome': r[1],
        'norm_nome': normalize_name(r[1]),
        'secretaria': r[2],
        'norm_sec': normalize_name(r[2]) if r[2] else None,
        'tipo': r[3]
    } for r in rows]

db_cargos = load_db_cargos()

# Load Excel File
try:
    xl = pd.ExcelFile(XLSX_PATH)
except PermissionError:
    print(f"[Aviso] Arquivo '{XLSX_PATH}' está aberto no Excel e travado. Lendo de 'temp_check.xlsx' como alternativa.")
    xl = pd.ExcelFile("temp_check.xlsx")

# Temporary data structure for parsed rows
grouped_cargos = {}

def add_to_group(cargo_name, secretaria, nome, matricula, portaria, vagas_existentes, simbolo_raw, recrutamento_raw, tipo_prov):
    norm_cargo = normalize_name(cargo_name)
    norm_sec = normalize_name(secretaria)
    key = (norm_cargo, norm_sec)
    
    if key not in grouped_cargos:
        grouped_cargos[key] = {
            'cargo_name': cargo_name,
            'secretaria': secretaria,
            'tipo_provimento': tipo_prov,
            'simbolos': [],
            'recrutamentos': [],
            'vagas': [],
            'occupants': []
        }
        
    group = grouped_cargos[key]
    
    if simbolo_raw:
        group['simbolos'].append(simbolo_raw)
    if recrutamento_raw:
        group['recrutamentos'].append(recrutamento_raw)
    if vagas_existentes is not None:
        group['vagas'].append(vagas_existentes)
        
    if nome:
        group['occupants'].append({
            'nome': nome,
            'matricula': matricula,
            'portaria': portaria,
            'simbolo_raw': simbolo_raw,
            'recrutamento_raw': recrutamento_raw
        })

# --- Tab 1: CC ---
print("\nProcessando aba 'CC'...")
df_cc = xl.parse('CC', header=None)
current_secretaria = "GABINETE DO PREFEITO"

for idx, row in df_cc.iloc[2:].iterrows():
    if pd.notna(row[0]) and pd.isna(row[1]) and pd.isna(row[2]) and pd.isna(row[3]):
        sec_val = str(row[0]).strip()
        if "QUADRO DE CARGOS" not in sec_val.upper():
            current_secretaria = sec_val
        continue

    cargo_name = clean_str(row[3])
    if not cargo_name:
        continue
        
    nome = clean_str(row[2])
    matricula = clean_matricula(row[0])
    portaria = clean_str(row[1])
    vagas_existentes = clean_int(row[4], None)
    simbolo_raw = clean_str(row[6])
    recrutamento_raw = clean_str(row[8])
    tipo_prov = 'Eletivo' if recrutamento_raw == 'ELETIVO' else 'Comissão'
    
    add_to_group(cargo_name, current_secretaria, nome, matricula, portaria, vagas_existentes, simbolo_raw, recrutamento_raw, tipo_prov)

# --- Tab 2: Conselho Tutelar ---
print("\nProcessando aba 'Conselho Tutelar'...")
df_ct = xl.parse('Conselho Tutelar', header=None)
for idx, row in df_ct.iloc[1:].iterrows():
    cargo_name = clean_str(row[3])
    if not cargo_name:
        continue
    nome = clean_str(row[2])
    matricula = clean_matricula(row[0])
    portaria = clean_str(row[1])
    vagas_existentes = clean_int(row[4], None)
    simbolo_raw = clean_str(row[6]) or 'CC-2'
    
    add_to_group(cargo_name, 'SECRETARIA MUNICIPAL DE PROMOÇÃO E BEM ESTAR SOCIAL', nome, matricula, portaria, vagas_existentes, simbolo_raw, 'Amplo', 'Comissão')

# --- Tab 3: Diretores de Escola ---
print("\nProcessando aba 'Diretores de Escola'...")
df_de = xl.parse('Diretores de Escola', header=None)
for idx, row in df_de.iterrows():
    cargo_name = clean_str(row[3])
    if not cargo_name:
        continue
    nome = clean_str(row[2])
    matricula = clean_matricula(row[0])
    portaria = clean_str(row[1])
    vagas_existentes = clean_int(row[4], None)
    simbolo_raw = clean_str(row[6])
    
    add_to_group(cargo_name, 'SECRETARIA MUNICIPAL DE EDUCAÇÃO', nome, matricula, portaria, vagas_existentes, simbolo_raw, 'Amplo', 'Comissão')

# Process grouped data and write to DB
total_imported = 0
total_cargos_created = 0

def encontrar_ou_criar_cargo_db(cargo_name, current_secretaria, tipo_prov, simbolo_raw, recrutamento_raw, total_vagas):
    norm_cargo = normalize_name(cargo_name)
    norm_sec = normalize_name(current_secretaria) if current_secretaria else None
    
    # 1. Tentar encontrar match exato por nome AND secretaria
    match = None
    for c in db_cargos:
        if c['norm_nome'] == norm_cargo and c['norm_sec'] == norm_sec:
            match = c
            break
            
    # 2. Se não encontrar, tentar encontrar match por nome com secretaria NULL
    if not match:
        for c in db_cargos:
            if c['norm_nome'] == norm_cargo and c['norm_sec'] is None:
                match = c
                # Vincula este cargo à secretaria no banco de dados
                con.execute("UPDATE Cargos SET secretaria = ? WHERE id = ?", (current_secretaria, c['id']))
                c['secretaria'] = current_secretaria
                c['norm_sec'] = norm_sec
                break
                
    simbolo_cargo = normalize_symbol(simbolo_raw)
    recrutamento_cargo = normalize_recrutamento(recrutamento_raw)
    if recrutamento_cargo == 'Outro':
        recrutamento_cargo = None
        
    global total_cargos_created
    if match:
        cargo_id = match['id']
        con.execute("""
            UPDATE Cargos
            SET tipo_provimento = ?,
                simbolo_vencimento = COALESCE(simbolo_vencimento, ?),
                recrutamento = COALESCE(recrutamento, ?),
                total_previstos = ?,
                secretaria = ?
            WHERE id = ?
        """, (tipo_prov, simbolo_cargo, recrutamento_cargo, total_vagas, current_secretaria, cargo_id))
    else:
        # Criar cargo novo
        cur = con.execute("""
            INSERT INTO Cargos
              (nome, situacao, tipo_provimento, simbolo_vencimento, recrutamento, total_previstos, total_ocupados, secretaria)
            VALUES (?, 'Em vigor', ?, ?, ?, ?, 0, ?)
        """, (cargo_name, tipo_prov, simbolo_cargo, recrutamento_cargo, total_vagas, current_secretaria))
        cargo_id = cur.lastrowid
        total_cargos_created += 1
        
        new_cargo = {
            'id': cargo_id,
            'nome': cargo_name,
            'norm_nome': norm_cargo,
            'secretaria': current_secretaria,
            'norm_sec': norm_sec,
            'tipo': tipo_prov
        }
        db_cargos.append(new_cargo)
        
    return cargo_id

print("\nGravando cargos e ocupantes no banco de dados...")
for key, g in grouped_cargos.items():
    cargo_name = g['cargo_name']
    secretaria = g['secretaria']
    tipo_prov = g['tipo_provimento']
    
    # Calculate sum of vacancies
    total_vagas = sum(g['vagas'])
    if total_vagas == 0:
        total_vagas = 1
        
    # Get the representative symbol and recruitment
    simbolo_raw = g['simbolos'][0] if g['simbolos'] else None
    recrutamento_raw = g['recrutamentos'][0] if g['recrutamentos'] else None
    
    cargo_id = encontrar_ou_criar_cargo_db(cargo_name, secretaria, tipo_prov, simbolo_raw, recrutamento_raw, total_vagas)
    
    # Insert occupants
    for occ in g['occupants']:
        con.execute("""
            INSERT INTO Ocupantes
              (cargo_id, nome, matricula, tipo_recrutamento, simbolo_vencimento, portaria, data_nomeacao)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
        """, (
            cargo_id, occ['nome'], occ['matricula'],
            normalize_recrutamento(occ['recrutamento_raw']),
            normalize_symbol(occ['simbolo_raw']),
            occ['portaria']
        ))
        total_imported += 1

con.commit()
con.close()

print("\n=== IMPORTAÇÃO CONCLUÍDA COM SUCESSO! ===")
print(f"Total de Ocupantes Importados: {total_imported}")
print(f"Novos Cargos Criados no Banco: {total_cargos_created}")
