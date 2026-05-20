# Script de teste limpo para geração de PDF

from relatorio_pdf import gerar_relatorio

mock_cargo = {
    'nome': 'ANALISTA EM TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO',
    'codigo_fopag': '1025',
    'situacao': 'Em vigor',
    'situacao_delib': 'Enviado',
    'tipo_provimento': 'Efetivo',
    'escolaridade': 'Curso Superior completo na área de TI com diploma reconhecido pelo MEC.',
    'carga_horaria': '40',
    'simbolo_vencimento': 'NS-3',
    'total_previstos': 15,
    'total_ocupados': 9,
    'saldo_vagas': 6,
    'atribuicoes': (
        'Desenvolver, implantar e prestar manutenção em sistemas de informação municipais. '
        'Gerenciar bancos de dados relacionais e infraestrutura de servidores em nuvem. '
        'Prestar assessoria técnica de TI nas diversas secretarias municipais e zelar pela segurança cibernética.'
    ),
    'recrutamento': 'Amplo',
    'restricao_exigencia': 'Registro no respectivo Conselho Regional de Engenharia ou TI se aplicável, e ausência de impedimentos legais.',
    'fonte_carga_horaria': 'Lei Complementar nº 28/2012, artigo 14',
    'fonte_atribuicoes': 'Decreto Municipal nº 5.802/2015, Anexo II'
}

mock_leis = [
    {'id': 1, 'numero': '1240', 'ano': 2012, 'acao': 'Cria', 'quantidade': 10, 'descricao': 'Criação de cargos para atender a demanda do novo Centro Tecnológico.'},
    {'id': 2, 'numero': '1410', 'ano': 2015, 'acao': 'Fixa', 'quantidade': None, 'descricao': 'Dispõe sobre o plano de cargos, carreiras e salários dos servidores da TI.'},
    {'id': 3, 'numero': '1552', 'ano': 2018, 'acao': 'Altera', 'quantidade': 5, 'descricao': 'Ampliação de vagas do quadro efetivo visando a digitalização dos serviços.'}
]

mock_fontes = [
    {'id': 1, 'tipo': 'Lei', 'numero': '1410', 'ano': 2015, 'detalhes': 'Regulamentação geral da jornada de trabalho para analistas.'}
]

print("Gerando PDF de teste em 'teste_relatorio_preview.pdf'...")
pdf_bytes = gerar_relatorio(mock_cargo, mock_leis, mock_fontes)

with open("teste_relatorio_preview.pdf", "wb") as f:
    f.write(pdf_bytes)

print("PDF gerado com sucesso!")
