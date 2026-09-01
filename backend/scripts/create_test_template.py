"""Creates a synthetic test PSD template with all editable layer types."""

from pathlib import Path

import numpy as np
import photoshopapi as psapi

OUTPUT = Path("gabaritos/caixa_35cm_teste.psd")
WIDTH, HEIGHT = 2000, 1200


def main():
    file = psapi.LayeredFile_8bit(psapi.enum.ColorMode.rgb, WIDTH, HEIGHT)
    cid = psapi.enum.ChannelID

    # --- Backgrounds ---
    grp_fundos = psapi.GroupLayer_8bit("FONDOS_TEMATICOS")
    file.add_layer(grp_fundos)

    bg_kraft = psapi.ImageLayer_8bit(
        {cid.red: np.full((HEIGHT, WIDTH), 194, np.uint8),
         cid.green: np.full((HEIGHT, WIDTH), 164, np.uint8),
         cid.blue: np.full((HEIGHT, WIDTH), 108, np.uint8)},
        "fundo_kraft_tradicional", width=WIDTH, height=HEIGHT, is_visible=True,
    )
    grp_fundos.add_layer(file, bg_kraft)

    bg_premium = psapi.ImageLayer_8bit(
        {cid.red: np.full((HEIGHT, WIDTH), 25, np.uint8),
         cid.green: np.full((HEIGHT, WIDTH), 25, np.uint8),
         cid.blue: np.full((HEIGHT, WIDTH), 25, np.uint8)},
        "fundo_preto_premium", width=WIDTH, height=HEIGHT, is_visible=False,
    )
    grp_fundos.add_layer(file, bg_premium)

    # --- Decorations (hidden by default) ---
    grp_deco = psapi.GroupLayer_8bit("DECORACOES_OPCIONAIS")
    file.add_layer(grp_deco)

    # One seal layer per face (BASE, BASE_2) — toggled together by the engine.
    for name, px in [("selo_entrega_rapida", 600), ("selo_entrega_rapida_2", 1600)]:
        selo = psapi.ImageLayer_8bit(
            {cid.red: np.full((80, 300), 220, np.uint8),
             cid.green: np.full((80, 300), 50, np.uint8),
             cid.blue: np.full((80, 300), 50, np.uint8)},
            name, width=300, height=80, pos_x=px, pos_y=50, is_visible=False,
        )
        grp_deco.add_layer(file, selo)

    forno = psapi.ImageLayer_8bit(
        {cid.red: np.full((100, 100), 180, np.uint8),
         cid.green: np.full((100, 100), 80, np.uint8),
         cid.blue: np.full((100, 100), 30, np.uint8)},
        "ilustracao_forno_lenha", width=100, height=100,
        pos_x=100, pos_y=1050, is_visible=False,
    )
    grp_deco.add_layer(file, forno)

    # --- Graphics ---
    # The box is DUPLA (two mirrored faces): each editable field gets one layer per face,
    # named BASE on face 1 and BASE_2 on face 2. The engine fills every matching layer.
    grp_graf = psapi.GroupLayer_8bit("ELEMENTOS_GRAFICOS")
    file.add_layer(grp_graf)

    for name, px in [("LOGO_CLIENTE", 300), ("LOGO_CLIENTE_2", 1300)]:
        logo = psapi.ImageLayer_8bit(
            {cid.red: np.full((200, 200), 128, np.uint8),
             cid.green: np.full((200, 200), 128, np.uint8),
             cid.blue: np.full((200, 200), 128, np.uint8)},
            name, width=200, height=200, pos_x=px, pos_y=400,
        )
        grp_graf.add_layer(file, logo)

    # --- Editable text layers (one per face) ---
    grp_textos = psapi.GroupLayer_8bit("TEXTOS_EDITAVEIS")
    file.add_layer(grp_textos)

    for name, text, size, x, y in [
        ("TEXTO_TELEFONE", "(11) 99999-9999", 36.0, 200.0, 900.0),
        ("TEXTO_INSTAGRAM", "@pizzaria_demo", 28.0, 200.0, 950.0),
        ("TEXTO_FRASE_OPCIONAL", "Bom Apetite!", 48.0, 200.0, 200.0),
        ("TEXTO_TELEFONE_2", "(11) 99999-9999", 36.0, 1200.0, 900.0),
        ("TEXTO_INSTAGRAM_2", "@pizzaria_demo", 28.0, 1200.0, 950.0),
        ("TEXTO_FRASE_OPCIONAL_2", "Bom Apetite!", 48.0, 1200.0, 200.0),
    ]:
        layer = psapi.TextLayer_8bit(
            name, text, font="ArialMT", font_size=size,
            fill_color=[1.0, 0.0, 0.0, 0.0],
            position_x=x, position_y=y,
        )
        grp_textos.add_layer(file, layer)

    # --- Die-cut lines (locked) ---
    grp_faca = psapi.GroupLayer_8bit("FACAS_E_CORTES", is_locked=True)
    file.add_layer(grp_faca)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    file.write(str(OUTPUT))
    print(f"Template criado: {OUTPUT}")


if __name__ == "__main__":
    main()
