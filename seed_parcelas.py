import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'quadro_pessoal.db')

from app import _popular_parcelas_iniciais

if __name__ == '__main__':
    print(f'Verificando e semeando parcelas em: {DB_PATH}')
    con = sqlite3.connect(DB_PATH)
    _popular_parcelas_iniciais(con)
    con.commit()
    con.close()
    print('Processo concluido com sucesso!')
