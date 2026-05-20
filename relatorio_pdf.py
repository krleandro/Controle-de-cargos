"""
FOPAG — Gerador de Relatórios PDF por Cargo
Página A4 · Design corporativo institucional
Dependência: fpdf2  (pip install fpdf2)
"""

from fpdf import FPDF
from fpdf.fonts import FontFace
from fpdf.enums import TableBordersLayout
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

BASE_DIR = Path(__file__).parent

# ── Paleta institucional ──────────────────────────────────────────────────────
AZUL_INST      = (20, 60, 120)    # Azul institucional escuro
AZUL_MEDIO     = (37, 99, 195)    # Azul médio
AZUL_CLARO     = (219, 234, 254)  # Azul claro (bg)
AZUL_SUAVE     = (239, 246, 255)  # Azul muito claro
CINZA_900      = (15, 23, 42)     # Quase preto
CINZA_700      = (51, 65, 85)
CINZA_600      = (71, 85, 105)
CINZA_500      = (100, 116, 139)
CINZA_400      = (148, 163, 184)
CINZA_300      = (203, 213, 225)
CINZA_200      = (226, 232, 240)
CINZA_100      = (241, 245, 249)
CINZA_50       = (248, 250, 252)
BRANCO         = (255, 255, 255)
VERDE_ESCURO   = (4, 120, 87)
VERDE_BG       = (209, 250, 229)
VERMELHO_ESC   = (185, 28, 28)
VERMELHO_BG    = (254, 226, 226)
AMBAR_ESC      = (161, 98, 7)
AMBAR_BG       = (254, 243, 199)
DOURADO        = (180, 145, 40)


def formatar_ch(ch, default_val="—"):
    if not ch:
        return default_val
    ch_str = str(ch).strip()
    if ch_str.isdigit():
        return f"{ch_str}h"
    return ch_str


class RelatorioCargoPDF(FPDF):
    """PDF A4 para relatório individual de cargo — layout institucional."""

    FONT_FAMILY = "Roboto"
    PAGE_W   = 210
    MARGIN_X = 20
    CONTENT_W = 170  # PAGE_W - 2*MARGIN_X

    def __init__(self):
        super().__init__(unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=25)
        self.set_margins(left=self.MARGIN_X, top=32, right=self.MARGIN_X)
        self.alias_nb_pages("{nb}")   # para "Página X de Y"
        self._setup_fonts()

    def _setup_fonts(self):
        import os
        base_dir = os.path.dirname(__file__)
        self.add_font("Roboto", "", os.path.join(base_dir, "Roboto-Regular.ttf"))
        self.add_font("Roboto", "B", os.path.join(base_dir, "Roboto-Bold.ttf"))
        self.add_font("Roboto", "I", os.path.join(base_dir, "Roboto-Italic.ttf"))

    def _set_font(self, style="", size=11):
        self.set_font(self.FONT_FAMILY, style, size)

    # ═══════════════════════════════════════════════════════════════════════════
    # HEADER / FOOTER (aplicados automaticamente)
    # ═══════════════════════════════════════════════════════════════════════════

    def header(self):
        if self.page == 1:
            return  # A capa tem seu próprio layout

        # Faixa azul escura no topo
        self.set_fill_color(*AZUL_INST)
        self.rect(x=0, y=0, w=self.PAGE_W, h=7, style="F")

        # Linha de acento dourada fina abaixo da faixa
        self.set_fill_color(*DOURADO)
        self.rect(x=0, y=7, w=self.PAGE_W, h=0.8, style="F")

        # Texto do header
        self.set_xy(self.MARGIN_X, 10)
        self._set_font("B", 9)
        self.set_text_color(*AZUL_MEDIO)
        self.cell(w=30, h=5, txt="FOPAG", ln=0)

        self._set_font("", 7.5)
        self.set_text_color(*CINZA_500)
        self.cell(w=90, h=5, txt="Sistema de Gestão de Cargos e Vagas", ln=0)

        # Direita: data
        self._set_font("I", 7.5)
        self.set_text_color(*CINZA_400)
        agora = datetime.now().strftime("%d/%m/%Y")
        self.cell(w=0, h=5, txt=agora, ln=1, align="R")

        self.set_x(self.MARGIN_X)
        self._set_font("", 7)
        self.set_text_color(*CINZA_400)
        self.cell(w=0, h=4, txt="Prefeitura Municipal de Miracema", ln=1)

        # Linha separadora sutil
        self.set_draw_color(*CINZA_200)
        self.set_line_width(0.15)
        self.line(self.MARGIN_X, 28, self.PAGE_W - self.MARGIN_X, 28)

    def footer(self):
        if self.page == 1:
            return  # A capa tem seu próprio rodapé

        self.set_y(-18)

        # Linha fina acima
        self.set_draw_color(*CINZA_200)
        self.set_line_width(0.15)
        self.line(self.MARGIN_X, self.get_y(), self.PAGE_W - self.MARGIN_X, self.get_y())
        self.ln(2.5)

        self._set_font("", 7)
        self.set_text_color(*CINZA_400)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(w=0, h=5, txt=f"FOPAG — Prefeitura Municipal de Miracema · Gerado em {agora}",
                  ln=0, align="L")
        self.cell(w=0, h=5, txt=f"Página {self.page_no()} de {{nb}}", ln=0, align="R")

    # ═══════════════════════════════════════════════════════════════════════════
    # PÁGINA DE CAPA
    # ═══════════════════════════════════════════════════════════════════════════

    def _capa(self, cargo: Dict[str, Any]):
        """Renderiza a página de capa institucional."""
        self.add_page()
        PAGE_H = 297

        # ── Faixa azul escura no topo ──────────────────────────────────────
        self.set_fill_color(*AZUL_INST)
        self.rect(x=0, y=0, w=self.PAGE_W, h=52, style="F")

        # Detalhe geométrico abstrato premium no banner do topo
        self.set_fill_color(30, 80, 150) # Azul médio
        self.polygon([(140, 0), (210, 0), (210, 52), (170, 52)], style="F")
        self.set_fill_color(40, 95, 175) # Azul mais claro de acento
        self.polygon([(175, 0), (210, 0), (210, 52), (195, 52)], style="F")

        # Linha dourada abaixo da faixa
        self.set_fill_color(*DOURADO)
        self.rect(x=0, y=52, w=self.PAGE_W, h=1.2, style="F")

        # Nome do sistema (alinhamento editorial à esquerda)
        self.set_xy(self.MARGIN_X, 12)
        self._set_font("B", 28)
        self.set_text_color(*BRANCO)
        self.cell(w=100, h=12, txt="FOPAG", align="L", ln=1)

        self.set_x(self.MARGIN_X)
        self._set_font("", 9.5)
        self.set_text_color(190, 215, 255)
        self.cell(w=100, h=6, txt="Sistema de Gestão de Cargos e Vagas", align="L", ln=1)

        self.set_x(self.MARGIN_X)
        self._set_font("I", 7.5)
        self.set_text_color(150, 185, 230)
        self.cell(w=100, h=5, txt="Prefeitura Municipal de Miracema", align="L", ln=1)

        # ── Área central de conteúdo ───────────────────────────────────────
        self.set_xy(0, 70)
        self._set_font("", 8)
        self.set_text_color(*CINZA_400)
        self.cell(w=self.PAGE_W, h=6, txt="RELATÓRIO INSTITUCIONAL DE CARGO", align="C", ln=1)

        # Linha decorativa centrada
        cx = self.PAGE_W / 2
        self.set_draw_color(*CINZA_300)
        self.set_line_width(0.3)
        self.line(cx - 35, 80, cx + 35, 80)

        # Nome do cargo
        nome = cargo.get("nome", "Cargo não identificado").upper()
        self.set_xy(self.MARGIN_X, 86)
        self._set_font("B", 18)
        self.set_text_color(*AZUL_INST)
        self.multi_cell(w=self.CONTENT_W, h=9, txt=nome, align="C")

        # Linha decorativa abaixo do nome
        y_after_nome = self.get_y() + 2
        self.set_draw_color(*AZUL_MEDIO)
        self.set_line_width(0.5)
        self.line(cx - 50, y_after_nome, cx + 50, y_after_nome)

        # Badges de situação e tipo
        sit   = cargo.get("situacao", "Em vigor")
        tipo  = cargo.get("tipo_provimento", "Efetivo")

        sit_cores = {
            "Em vigor": (AZUL_SUAVE, AZUL_MEDIO),
            "Extinto":  (CINZA_100, CINZA_600),
            "Revogado": (VERMELHO_BG, VERMELHO_ESC),
        }
        tipo_cores = {
            "Efetivo":  (AZUL_SUAVE, AZUL_INST),
            "Comissão": (AMBAR_BG, AMBAR_ESC),
            "Comissao": (AMBAR_BG, AMBAR_ESC),
        }

        bg_s, txt_s = sit_cores.get(sit, sit_cores["Em vigor"])
        bg_t, txt_t = tipo_cores.get(tipo, tipo_cores["Efetivo"])

        y_badges = y_after_nome + 8
        self.set_y(y_badges)

        # Renderiza dois badges centralizados
        self._set_font("B", 8.5)
        w_s = self.get_string_width(sit) + 12
        w_t = self.get_string_width(tipo) + 12
        gap = 6
        total_w = w_s + w_t + gap
        x_start = (self.PAGE_W - total_w) / 2
        badge_h = 7.5

        self.set_fill_color(*bg_s)
        self.rect(x_start, y_badges, w_s, badge_h, style="F")
        self.set_draw_color(*txt_s)
        self.set_line_width(0.3)
        self.rect(x_start, y_badges, w_s, badge_h, style="D")
        self.set_xy(x_start, y_badges + 1.5)
        self.set_text_color(*txt_s)
        self.cell(w=w_s, h=badge_h - 3, txt=sit, align="C", ln=0)

        x2 = x_start + w_s + gap
        self.set_fill_color(*bg_t)
        self.rect(x2, y_badges, w_t, badge_h, style="F")
        self.set_draw_color(*txt_t)
        self.set_line_width(0.3)
        self.rect(x2, y_badges, w_t, badge_h, style="D")
        self.set_xy(x2, y_badges + 1.5)
        self.set_text_color(*txt_t)
        self.cell(w=w_t, h=badge_h - 3, txt=tipo, align="C", ln=1)

        # ── Painel de sumário de quantitativos ────────────────────────────
        prev  = cargo.get("total_previstos", 0) or 0
        ocup  = cargo.get("total_ocupados",  0) or 0
        saldo = cargo.get("saldo_vagas", prev - ocup)

        if saldo < 0:
            cor_saldo, label_saldo = VERMELHO_ESC, "Déficit"
        elif saldo == 0:
            cor_saldo, label_saldo = AMBAR_ESC, "Esgotado"
        else:
            cor_saldo, label_saldo = VERDE_ESCURO, "Disponível"

        panel_y = y_badges + badge_h + 14
        panel_h = 38
        panel_x = self.MARGIN_X + 20
        panel_w = self.CONTENT_W - 40

        # Sombra leve
        self.set_fill_color(220, 228, 240)
        self.rect(panel_x + 1.5, panel_y + 1.5, panel_w, panel_h, style="F")

        # Card principal
        self.set_fill_color(*BRANCO)
        self.set_draw_color(*CINZA_200)
        self.set_line_width(0.3)
        self.rect(panel_x, panel_y, panel_w, panel_h, style="FD")

        # Borda colorida superior
        self.set_fill_color(*cor_saldo)
        self.rect(panel_x, panel_y, panel_w, 2.5, style="F")

        col_w = panel_w / 3
        metrics = [
            ("VAGAS PREVISTAS", str(prev),   CINZA_500, CINZA_900),
            ("VAGAS OCUPADAS",  str(ocup),   CINZA_500, CINZA_900),
            ("SALDO",           f"{saldo:+d}", cor_saldo, cor_saldo),
        ]

        for i, (lbl, val, lbl_col, val_col) in enumerate(metrics):
            cx_col = panel_x + i * col_w + 4
            cy_lbl = panel_y + 7

            # Separador vertical entre colunas
            if i > 0:
                self.set_draw_color(*CINZA_200)
                self.set_line_width(0.2)
                self.line(panel_x + i * col_w, panel_y + 5,
                          panel_x + i * col_w, panel_y + panel_h - 5)

            self.set_xy(cx_col, cy_lbl)
            self._set_font("", 6.5)
            self.set_text_color(*lbl_col)
            self.cell(w=col_w - 8, h=4, txt=lbl, ln=1, align="C")

            self.set_x(cx_col)
            self._set_font("B", 22 if i < 2 else 24)
            self.set_text_color(*val_col)
            self.cell(w=col_w - 8, h=13, txt=val, ln=1, align="C")

            if i == 2:
                self.set_x(cx_col)
                self._set_font("B", 7)
                self.set_text_color(*cor_saldo)
                self.cell(w=col_w - 8, h=4, txt=label_saldo, ln=1, align="C")

        # ── Dados-chave na capa (Grid 3x2 Simétrico e Preciso) ────────────
        info_y = panel_y + panel_h + 12
        self._divider_line(info_y - 2)

        items = [
            ("Código FOPAG:",    cargo.get("codigo_fopag") or "—"),
            ("Tipo:",            tipo),
            ("Carga Horária:",   formatar_ch(cargo.get("carga_horaria"))),
            ("Recrutamento:",    cargo.get("recrutamento") or "—"),
            ("Símbolo Venc.:",   cargo.get("simbolo_vencimento") or "—"),
            ("Deliberação 359:", (cargo.get("situacao_delib") or "Não Enviado").title()),
        ]

        col1_x = self.MARGIN_X
        col2_x = self.PAGE_W / 2 + 5
        grid_col_w = self.CONTENT_W / 2

        self.set_y(info_y)
        for i, (lbl, val) in enumerate(items):
            col_idx = i % 2
            row_idx = i // 2
            col_x = col1_x if col_idx == 0 else col2_x
            row_y = info_y + row_idx * 7.5

            self.set_xy(col_x, row_y)
            self._set_font("", 7.5)
            self.set_text_color(*CINZA_500)
            self.cell(w=32, h=5, txt=lbl, ln=0)

            self._set_font("B", 8.5)
            self.set_text_color(*CINZA_900)
            avail = grid_col_w - 36
            self.cell(w=avail, h=5, txt=str(val), ln=0)

        # ── Rodapé da capa ────────────────────────────────────────────────
        self.set_fill_color(*AZUL_INST)
        self.rect(x=0, y=PAGE_H - 18, w=self.PAGE_W, h=18, style="F")
        self.set_fill_color(*DOURADO)
        self.rect(x=0, y=PAGE_H - 18, w=self.PAGE_W, h=0.8, style="F")

        # Detalhe geométrico no rodapé correspondente ao topo
        self.set_fill_color(30, 80, 150)
        self.polygon([(160, PAGE_H - 18), (210, PAGE_H - 18), (210, PAGE_H), (175, PAGE_H)], style="F")

        self.set_xy(self.MARGIN_X, PAGE_H - 13)
        self._set_font("", 7.5)
        self.set_text_color(180, 210, 255)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(w=0, h=5, txt=f"Documento gerado em {agora} · Confidencial · Uso interno",
                  align="C", ln=0)

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPONENTES DE CONTEÚDO
    # ═══════════════════════════════════════════════════════════════════════════

    def _divider_line(self, y=None):
        """Linha divisória sutil."""
        y = y or self.get_y()
        self.set_draw_color(*CINZA_200)
        self.set_line_width(0.15)
        self.line(self.MARGIN_X, y, self.PAGE_W - self.MARGIN_X, y)

    def _section_title(self, title: str):
        """Título de seção com fundo azul suave e barra à esquerda com prevenção de quebra órfã."""
        # Se restarem menos de 45mm na página (descontando o rodapé), força nova página
        if self.get_y() > (self.h - 45):
            self.add_page()

        self.ln(3)
        y = self.get_y()
        h = 8.5

        # Fundo suave
        self.set_fill_color(*AZUL_SUAVE)
        self.rect(x=self.MARGIN_X, y=y, w=self.CONTENT_W, h=h, style="F")

        # Barra azul à esquerda
        self.set_fill_color(*AZUL_MEDIO)
        self.rect(x=self.MARGIN_X, y=y, w=2.5, h=h, style="F")

        # Texto
        self.set_xy(self.MARGIN_X + 6, y + 1.5)
        self._set_font("B", 10)
        self.set_text_color(*AZUL_INST)
        self.cell(w=0, h=h - 3, txt=title.upper(), ln=1)
        self.ln(2)

    def _info_panel_start(self):
        """Inicia um painel de informações com fundo cinza claro."""
        self._panel_start_y = self.get_y()

    def _info_panel_end(self):
        """Fecha visualmente o painel de informações."""
        if hasattr(self, "_panel_start_y"):
            end_y = self.get_y()
            h = end_y - self._panel_start_y
            # Borda sutil ao redor do bloco
            self.set_draw_color(*CINZA_200)
            self.set_line_width(0.2)
            self.rect(self.MARGIN_X, self._panel_start_y, self.CONTENT_W, h, style="D")
        self.ln(2)

    def _render_grid_panel(self, items: List[tuple]):
        """Renderiza um painel em grid de 2 colunas para metadados curtos."""
        col_w = self.CONTENT_W / 2
        row_h = 7.5
        
        y_start = self.get_y()
        num_rows = (len(items) + 1) // 2
        panel_h = num_rows * row_h + 3
        
        self.set_fill_color(*CINZA_50)
        self.set_draw_color(*CINZA_200)
        self.set_line_width(0.2)
        self.rect(self.MARGIN_X, y_start, self.CONTENT_W, panel_h, style="FD")
        
        # Faixa azul sutil no topo
        self.set_fill_color(*AZUL_MEDIO)
        self.rect(self.MARGIN_X, y_start, self.CONTENT_W, 1.2, style="F")
        
        self.ln(2.5)
        
        for i, (lbl, val) in enumerate(items):
            col_idx = i % 2
            row_idx = i // 2
            
            x_pos = self.MARGIN_X + col_idx * col_w + 4
            y_pos = y_start + 2.5 + row_idx * row_h
            
            # Linha vertical separadora
            if col_idx > 0:
                self.set_draw_color(*CINZA_200)
                self.set_line_width(0.15)
                self.line(self.MARGIN_X + col_w, y_start + 3, self.MARGIN_X + col_w, y_start + panel_h - 3)
            
            self.set_xy(x_pos, y_pos)
            self._set_font("", 7.5)
            self.set_text_color(*CINZA_500)
            self.cell(w=38, h=row_h - 1, txt=f"{lbl}:", ln=0)
            
            self._set_font("B", 8)
            self.set_text_color(*CINZA_900)
            
            # Evita crashes e garante formatação limpa
            val_str = str(val).strip() if val is not None else "—"
            if val_str == "" or val_str == "None":
                val_str = "—"
            self.cell(w=col_w - 46, h=row_h - 1, txt=val_str, ln=0)
            
        self.set_y(y_start + panel_h + 4)

    def _render_text_block(self, label: str, text: str):
        """Renderiza um bloco moderno de texto longo com borda dourada lateral decorativa nativa e padding."""
        val_str = str(text).strip() if text is not None else ""
        if not val_str or val_str == "None" or val_str == "—":
            return
            
        self.ln(2.5)
        
        # Salva o c_margin original
        old_margin = self.c_margin
        # Configura padding esquerdo de 4.0mm para afastar o texto da borda dourada
        self.c_margin = 4.0
        
        # Configura cor da borda para DOURADO e largura da linha
        self.set_draw_color(*DOURADO)
        self.set_line_width(1.0)
        
        # Título do bloco com borda esquerda nativa
        self._set_font("B", 7.5)
        self.set_text_color(*AZUL_INST)
        self.set_x(self.MARGIN_X)
        self.cell(w=self.CONTENT_W, h=4, txt=label.upper(), border="L", ln=1)
        
        self.ln(1)
        self._set_font("", 8)
        self.set_text_color(*CINZA_700)
        
        # Texto com borda esquerda nativa
        self.set_x(self.MARGIN_X)
        self.multi_cell(w=self.CONTENT_W, h=4.5, txt=val_str, border="L", ln=1)
        
        # Restaura c_margin e largura de linha padrão
        self.c_margin = old_margin
        self.set_line_width(0.2)
        self.ln(2)

    def _info_row(self, label: str, value: str, alt: bool = False, width_label: float = 58):
        """Linha de informação dentro de painel, com fundo alternado."""
        row_h = 6.2
        row_y = self.get_y()

        # Fundo alternado
        if alt:
            self.set_fill_color(*CINZA_50)
            self.rect(self.MARGIN_X, row_y, self.CONTENT_W, row_h, style="F")

        self.set_x(self.MARGIN_X + 4)
        self._set_font("", 7.5)
        self.set_text_color(*CINZA_500)
        self.cell(w=width_label, h=row_h, txt=label, ln=0)

        self._set_font("B", 8.5)
        self.set_text_color(*CINZA_900)
        self.multi_cell(w=0, h=row_h, txt=str(value) if value else "—", ln=1)

    def _badge_inline(self, text: str, bg_rgb: tuple, text_rgb: tuple):
        """Badge inline."""
        self._set_font("B", 8)
        self.set_text_color(*text_rgb)
        pad = 3.5
        w_text = self.get_string_width(text) + pad * 2
        h_badge = 6
        x, y = self.get_x(), self.get_y()
        self.set_fill_color(*bg_rgb)
        self.rect(x, y, w_text, h_badge, style="F")
        self.set_draw_color(*text_rgb)
        self.set_line_width(0.2)
        self.rect(x, y, w_text, h_badge, style="D")
        self.set_xy(x + pad, y + 1.2)
        self.cell(w=w_text - pad * 2, h=h_badge - 2.4, txt=text, ln=0, align="C")
        self.set_xy(x + w_text + 4, y)
        return w_text + 4

    def _saldo_box(self, previstos: int, ocupados: int, saldo: int):
        """Box de quantitativos — três KPI cards horizontais com prevenção de quebra órfã."""
        if self.get_y() > (self.h - 45):
            self.add_page()

        if saldo < 0:
            cor_s, label_s = VERMELHO_ESC, "Déficit"
        elif saldo == 0:
            cor_s, label_s = AMBAR_ESC, "Esgotado"
        else:
            cor_s, label_s = VERDE_ESCURO, "Disponível"

        box_y = self.get_y()
        box_h = 30
        col_w = self.CONTENT_W / 3

        cards = [
            ("VAGAS PREVISTAS", str(previstos), CINZA_500, CINZA_900),
            ("VAGAS OCUPADAS",  str(ocupados),  CINZA_500, CINZA_900),
            ("SALDO DE VAGAS",  f"{saldo:+d}",  cor_s,     cor_s),
        ]

        for i, (lbl, val, lbl_col, val_col) in enumerate(cards):
            cx = self.MARGIN_X + i * col_w
            # Fundo do card
            self.set_fill_color(*CINZA_50)
            self.set_draw_color(*CINZA_200)
            self.set_line_width(0.2)
            self.rect(cx, box_y, col_w, box_h, style="FD")

            # Barra colorida no topo
            top_col = cor_s if i == 2 else AZUL_MEDIO
            self.set_fill_color(*top_col)
            self.rect(cx, box_y, col_w, 2, style="F")

            # Label
            self.set_xy(cx + 2, box_y + 5)
            self._set_font("", 6.5)
            self.set_text_color(*lbl_col)
            self.cell(w=col_w - 4, h=4, txt=lbl, ln=1, align="C")

            # Valor
            self.set_x(cx + 2)
            self._set_font("B", 20 if i < 2 else 22)
            self.set_text_color(*val_col)
            self.cell(w=col_w - 4, h=12, txt=val, ln=1, align="C")

            # Sublabel para saldo
            if i == 2:
                self.set_x(cx + 2)
                self._set_font("B", 7)
                self.set_text_color(*cor_s)
                self.cell(w=col_w - 4, h=4, txt=label_s, ln=1, align="C")

        self.set_y(box_y + box_h + 4)

    def _leis_table(self, leis: List[Dict[str, Any]]):
        """Tabela de leis com design refinado."""
        if not leis:
            self.ln(2)
            self._set_font("I", 9)
            self.set_text_color(*CINZA_400)
            self.cell(w=0, h=6, txt="Nenhuma lei vinculada a este cargo.", ln=1)
            return

        self.ln(1)

        def acao_style(acao: str):
            if acao == "Cria":
                return FontFace(color=VERDE_ESCURO, emphasis="B", fill_color=VERDE_BG)
            elif acao == "Extingue":
                return FontFace(color=VERMELHO_ESC, emphasis="B", fill_color=VERMELHO_BG)
            elif acao == "Fixa":
                return FontFace(color=AMBAR_ESC, emphasis="B", fill_color=AMBAR_BG)
            elif acao == "Altera":
                return FontFace(color=AZUL_INST, emphasis="B", fill_color=AZUL_CLARO)
            else:
                return FontFace(color=CINZA_600, emphasis="B", fill_color=CINZA_100)

        heading_face = FontFace(
            emphasis="B",
            color=BRANCO,
            fill_color=AZUL_INST,
        )

        col_widths = (26, 14, 26, 18, 86)
        self._set_font("", 8)

        with self.table(
            col_widths=col_widths,
            text_align=("CENTER", "CENTER", "CENTER", "CENTER", "LEFT"),
            v_align="MIDDLE",
            line_height=5.8,
            headings_style=heading_face,
            borders_layout=TableBordersLayout.ALL,
        ) as table:
            table.row(["Nº Lei", "Ano", "Ação", "Qtd", "Descrição / Ementa"])

            for i, lei in enumerate(leis):
                acao   = lei.get("acao", "Outro")
                desc   = lei.get("descricao") or "—"
                qtd    = str(lei.get("quantidade") or "—")
                ano    = str(lei.get("ano") or "—")
                numero = str(lei.get("numero", "—"))

                bg = CINZA_50 if i % 2 == 0 else BRANCO
                data_face = FontFace(fill_color=bg)

                row = table.row()
                row.cell(numero, style=data_face)
                row.cell(ano, style=data_face)
                row.cell(acao, style=acao_style(acao))
                row.cell(qtd, style=data_face)
                row.cell(desc, style=data_face)

        self.ln(2)

    # ═══════════════════════════════════════════════════════════════════════════
    # MONTAGEM DO RELATÓRIO (página de conteúdo)
    # ═══════════════════════════════════════════════════════════════════════════

    def _pagina_conteudo(self, cargo: Dict[str, Any], leis: List[Dict[str, Any]], fontes: List[Dict[str, Any]]):
        """Monta as páginas de conteúdo após a capa."""
        self.add_page()

        nome = cargo.get("nome", "Cargo não identificado")
        sit  = cargo.get("situacao", "Em vigor")
        tipo = cargo.get("tipo_provimento", "Efetivo")

        # ── Título da página de conteúdo ──
        self._set_font("B", 14)
        self.set_text_color(*CINZA_900)
        self.cell(w=0, h=8, txt="Relatório de Cargo", ln=1)

        self._set_font("B", 11)
        self.set_text_color(*AZUL_MEDIO)
        self.multi_cell(w=0, h=6, txt=nome, ln=1)
        self.ln(0.5)

        # Badges
        sit_cores = {
            "Em vigor": (AZUL_SUAVE, AZUL_MEDIO),
            "Extinto":  (CINZA_100, CINZA_600),
            "Revogado": (VERMELHO_BG, VERMELHO_ESC),
        }
        tipo_cores = {
            "Efetivo":  (AZUL_SUAVE, AZUL_INST),
            "Comissão": (AMBAR_BG, AMBAR_ESC),
            "Comissao": (AMBAR_BG, AMBAR_ESC),
        }
        bg_s, txt_s = sit_cores.get(sit, sit_cores["Em vigor"])
        bg_t, txt_t = tipo_cores.get(tipo, tipo_cores["Efetivo"])
        self._badge_inline(sit, bg_s, txt_s)
        self._badge_inline(tipo, bg_t, txt_t)
        self.ln(8)

        # ── Seção 1: Identificação e Regime ──
        self._section_title("Identificação e Regime")
        ident_items = [
            ("Código FOPAG", cargo.get("codigo_fopag")),
            ("Tipo de Provimento", tipo),
            ("Situação", sit),
            ("Situação Delib. 359", (cargo.get("situacao_delib") or "não enviado").title()),
            ("Recrutamento", cargo.get("recrutamento")),
            ("Símbolo Vencimento", cargo.get("simbolo_vencimento")),
            ("Carga Horária Semanal", formatar_ch(cargo.get("carga_horaria"))),
            ("Fonte da Carga Horária", cargo.get("fonte_carga_horaria")),
        ]
        self._render_grid_panel(ident_items)

        # ── Seção 2: Requisitos e Atribuições ──
        self._section_title("Requisitos e Atribuições")
        self._render_text_block("Requisitos de Escolaridade", cargo.get("escolaridade"))
        self._render_text_block("Restrições e Exigências de Ingresso", cargo.get("restricao_exigencia"))
        self._render_text_block("Fonte das Atribuições", cargo.get("fonte_atribuicoes"))
        self._render_text_block("Atribuições Descritivas do Cargo", cargo.get("atribuicoes"))

        # ── Seção 3: Quantitativos do Quadro ──
        self._section_title("Quantitativos do Quadro")
        prev  = cargo.get("total_previstos", 0) or 0
        ocup  = cargo.get("total_ocupados",  0) or 0
        saldo = cargo.get("saldo_vagas", prev - ocup)
        self._saldo_box(prev, ocup, saldo)

        # ── Seção 4: Fontes Adicionais de Carga Horária ──
        if fontes:
            self._section_title("Fontes Adicionais de Carga Horária")
            self._info_panel_start()
            for idx, f in enumerate(fontes):
                det = f.get("detalhes") or f"{f.get('tipo', '—')} {f.get('numero', '')}"
                self._info_row(f.get("tipo", "Fonte"), det, alt=idx % 2 == 0)
            self._info_panel_end()

        # ── Seção 5: Histórico Legislativo ──
        self._section_title("Histórico Legislativo")
        self._leis_table(leis)

    # ═══════════════════════════════════════════════════════════════════════════
    # ENTRADA PÚBLICA
    # ═══════════════════════════════════════════════════════════════════════════

    def montar(self, cargo: Dict[str, Any], leis: List[Dict[str, Any]], fontes: List[Dict[str, Any]]):
        """Gera a capa e as páginas de conteúdo."""
        self._capa(cargo)
        self._pagina_conteudo(cargo, leis, fontes)

        # Metadados do documento
        nome_cargo = cargo.get("nome", "Cargo")
        self.set_title(f"Relatório FOPAG — {nome_cargo}")
        self.set_author("FOPAG — Prefeitura Municipal de Miracema")
        self.set_subject(f"Relatório de Cargo: {nome_cargo}")
        self.set_creator("FOPAG v1.0")
        self.set_keywords("FOPAG cargo vaga quadro pessoal Miracema")


def gerar_relatorio(cargo: dict, leis: list, fontes: list) -> bytes:
    """Gera o PDF e retorna os bytes prontos para download."""
    pdf = RelatorioCargoPDF()
    pdf.montar(cargo, leis, fontes)
    return bytes(pdf.output(dest="S"))
