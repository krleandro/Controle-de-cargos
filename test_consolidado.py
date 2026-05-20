# Script de teste para geração do Relatório Consolidado
import sqlite3, os
from datetime import datetime
from relatorio_pdf import gerar_relatorio_consolidado

DB_PATH = "quadro_pessoal.db"

def test():
    print("Conectando ao banco de dados...")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    
    try:
        print("Consultando estatísticas...")
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
        
        print("Consultando provimentos...")
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
        
        print("Consultando todos os cargos...")
        res_cargos = con.execute("SELECT * FROM vw_SaldoVagas ORDER BY nome COLLATE NOCASE").fetchall()
        cargos = [dict(r) for r in res_cargos]
        
    finally:
        con.close()
        
    print(f"Estatísticas Gerais: {stats}")
    print(f"Estatísticas Provimento: {prov_stats}")
    print(f"Total de cargos para tabela: {len(cargos)}")
    
    print("Gerando Relatório Consolidado...")
    try:
        pdf_bytes = gerar_relatorio_consolidado(stats, prov_stats, cargos)
        output_filename = "teste_relatorio_consolidado_preview.pdf"
        with open(output_filename, "wb") as f:
            f.write(pdf_bytes)
        print(f"Relatório Consolidado gerado com sucesso em '{output_filename}'!")
    except Exception as e:
        print(f"Erro ao gerar Relatório Consolidado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
