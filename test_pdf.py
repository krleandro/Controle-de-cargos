# Script de teste limpo para geração de PDF

from relatorio_pdf import gerar_relatorio

mock_cargo = {
    'nome': 'Advogado do Centro de Referência Especializada de Assistência Social',
    'codigo_fopag': '409',
    'situacao': 'Em vigor',
    'situacao_delib': 'não enviado',
    'tipo_provimento': 'Efetivo',
    'escolaridade': 'Superior',
    'carga_horaria': '20',
    'simbolo_vencimento': 'P-34',
    'total_previstos': 1,
    'total_ocupados': 1,
    'saldo_vagas': 0,
    'atribuicoes': 'Lei complementar Municipal Nº 1465/2013 - Art. 30, X',
    'recrutamento': None,
    'restricao_exigencia': 'Superior',
    'fonte_carga_horaria': 'Edital 2023 - BO 375',
    'fonte_atribuicoes': None
}

mock_leis = [
    {'id': 1, 'cargo_id': 1, 'numero': '1465', 'ano': 2013, 'descricao': '1465/13 - Revogada parcialmente pela Lei 1632/16', 'acao': 'Cria', 'quantidade': 1, 'texto_original': 'Cria 1'}
]

mock_fontes = [
    {'id': 1, 'cargo_id': 1, 'tipo': 'Edital', 'numero': '2023', 'ano': None, 'detalhes': 'Edital 2023 - BO 375'}
]

print("Gerando PDF de teste em 'teste_relatorio_preview.pdf'...")
pdf_bytes = gerar_relatorio(mock_cargo, mock_leis, mock_fontes)

with open("teste_relatorio_preview.pdf", "wb") as f:
    f.write(pdf_bytes)

print("PDF gerado com sucesso!")

