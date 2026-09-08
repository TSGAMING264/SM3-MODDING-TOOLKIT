from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from sm3_toolkit import paths
from sm3_toolkit.i18n import tr
from sm3_toolkit.theme import COLORS


class AboutInfoTab(ttk.Frame):
    """Release About / Info page with visual creator and contributor credits."""

    CREDIT_PEOPLE = (
        (
            "Devryx",
            "WOS Toolkit developer",
            "devryx_avatar.png",
        ),
        (
            "Haruse",
            "WOS Addon developer",
            "haruse_avatar.png",
        ),
        (
            "Kirbystealer",
            "ExWOS contributor",
            "kirbystealer_avatar.png",
        ),
        (
            "UndeadFrankie",
            "DR2 Tool developer",
            "undeadfrankie_avatar.png",
        ),
        (
            "ArchiverOfTriviality",
            "WOSTweaks contributor",
            "arc_avatar.png",
        ),
    )

    COMMUNITY_PEOPLE = (
        (
            "Tmprogamer",
            "xeSM3 beta tester",
            "tmprogamer_avatar.png",
        ),
        (
            "Kujo-Jotaro777",
            "xeSM3 community contributor",
            "kujo_jotaro777_avatar.png",
        ),
        (
            "(N-Trki)",
            "M.U.G.E.N Developer and SM2 & Ultimate Spider-Man modder",
            "n_trki_avatar.png",
        ),
        (
            "SpiderGlider",
            "Sound Editor inspiration through Spider-Man 3 audio mod work",
            "spiderglider_avatar.png",
        ),
        (
            "AkyrosXD",
            "RaimiHook creator / Debug Recreation creator",
            "akyrosxd_avatar.png",
        ),
        (
            "Bread",
            "IDA coding for SM3",
            "bread_avatar.png",
        ),
    )

    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame")
        self.app_state = app_state
        self._images: dict[str, tk.PhotoImage] = {}
        self._credit_cards: list[tuple[ttk.Frame, ttk.Label]] = []
        self._community_cards: list[tuple[ttk.Frame, ttk.Label]] = []
        self._credit_columns = 0
        self._community_columns = 0
        self._canvas_window = None
        self._wos_stacked: bool | None = None
        self._build()

    def _load_image(self, key: str, path: Path) -> tk.PhotoImage | None:
        try:
            if not path.exists():
                return None
            image = tk.PhotoImage(file=str(path))
            self._images[key] = image
            return image
        except Exception:
            return None

    def _build(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.page_canvas = tk.Canvas(
            self,
            highlightthickness=0,
            borderwidth=0,
            bg=COLORS.get("bg", "#171717"),
        )
        page_scroll = ttk.Scrollbar(self, orient="vertical", command=self.page_canvas.yview)
        self.page_canvas.configure(yscrollcommand=page_scroll.set)
        self.page_canvas.grid(row=0, column=0, sticky="nsew")
        page_scroll.grid(row=0, column=1, sticky="ns")

        self.page = ttk.Frame(self.page_canvas, style="Body.TFrame", padding=16)
        self.page.columnconfigure(0, weight=1)
        self._canvas_window = self.page_canvas.create_window((0, 0), window=self.page, anchor="nw")

        ttk.Label(self.page, text="SM3 MODDING TOOLKIT", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        creator = ttk.Frame(self.page, style="Panel.TFrame", padding=12)
        creator.grid(row=1, column=0, sticky="ew", pady=(6, 12))
        creator.columnconfigure(1, weight=1)

        profile = self._load_image("tsgaming264", paths.TSGAMING264_PROFILE_IMAGE)
        if profile is not None:
            ttk.Label(creator, image=profile, style="Panel.TLabel").grid(
                row=0, column=0, rowspan=3, sticky="nw", padx=(0, 14)
            )

        ttk.Label(
            creator,
            text="Created by TSGAMING264",
            style="Panel.TLabel",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(
            creator,
            text="Creator / SM3 Toolkit",
            style="Panel.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.subtitle_label = ttk.Label(
            creator,
            text="",
            style="Panel.TLabel",
            font=("Segoe UI", 9),
            justify="left",
        )
        self.subtitle_label.grid(row=2, column=1, sticky="ew", pady=(5, 0))

        ttk.Label(self.page, text="SPECIAL THANKS / INSPIRATION", style="SectionTitle.TLabel").grid(
            row=2, column=0, sticky="w", pady=(2, 6)
        )

        # Main WOS Toolkit shout-out. b5 is the WOS Toolkit image, not a person avatar.
        self.wos_spotlight = ttk.Frame(self.page, style="Panel.TFrame", padding=12)
        self.wos_spotlight.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self.wos_spotlight.columnconfigure(1, weight=1)

        wos_banner = self._load_image(
            "wos_toolkit_banner",
            paths.ABOUT_CREDIT_IMAGES_DIR / "wos_toolkit_banner.png",
        )
        self.wos_banner_label = ttk.Label(self.wos_spotlight, style="Panel.TLabel")
        if wos_banner is not None:
            self.wos_banner_label.configure(image=wos_banner)
        else:
            self.wos_banner_label.configure(text="WOS TOOLKIT", font=("Segoe UI", 18, "bold"))

        self.wos_copy = ttk.Frame(self.wos_spotlight, style="Panel.TFrame")
        ttk.Label(
            self.wos_copy,
            text="WEB OF SHADOWS TOOLKIT",
            style="Panel.TLabel",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.wos_shoutout_label = ttk.Label(
            self.wos_copy,
            text=(
                "Special shout-out to the WOS Toolkit and its developers / contributors. "
                "Their work helped inspire the layout, tools, and workflow direction of the SM3 Toolkit."
            ),
            style="Panel.TLabel",
            font=("Segoe UI", 10),
            justify="left",
            anchor="nw",
        )
        self.wos_shoutout_label.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        self.wos_copy.columnconfigure(0, weight=1)

        ttk.Label(
            self.page,
            text="WOS TOOLKIT CONTRIBUTORS",
            style="SectionTitle.TLabel",
        ).grid(row=4, column=0, sticky="w", pady=(2, 4))

        self.credit_intro = ttk.Label(
            self.page,
            text=(
                "Special thanks to the WOS Toolkit contributors below."
            ),
            style="Muted.TLabel",
            justify="left",
        )
        self.credit_intro.grid(row=5, column=0, sticky="ew", pady=(0, 8))

        self.credits = ttk.Frame(self.page, style="Body.TFrame")
        self.credits.grid(row=6, column=0, sticky="ew")

        for name, role, filename in self.CREDIT_PEOPLE:
            card = ttk.Frame(self.credits, style="Panel.TFrame", padding=10)
            card.columnconfigure(0, weight=1)
            image_path = paths.ABOUT_CREDIT_IMAGES_DIR / filename
            avatar = self._load_image(name, image_path)
            if avatar is not None:
                ttk.Label(card, image=avatar, style="Panel.TLabel").grid(row=0, column=0, pady=(0, 7))
            else:
                ttk.Label(
                    card,
                    text=name[:2].upper(),
                    style="Panel.TLabel",
                    font=("Segoe UI", 22, "bold"),
                ).grid(row=0, column=0, pady=(24, 31))

            ttk.Label(
                card,
                text=name,
                style="Panel.TLabel",
                font=("Segoe UI", 11, "bold"),
                anchor="center",
            ).grid(row=1, column=0, sticky="ew")
            role_label = ttk.Label(
                card,
                text=role,
                style="Panel.TLabel",
                font=("Segoe UI", 9),
                justify="center",
                anchor="center",
            )
            role_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))
            self._credit_cards.append((card, role_label))

        ttk.Separator(self.page, orient="horizontal").grid(row=7, column=0, sticky="ew", pady=(16, 10))
        ttk.Label(
            self.page,
            text="ADDITIONAL COMMUNITY / xeSM3 CREDITS",
            style="SectionTitle.TLabel",
        ).grid(row=8, column=0, sticky="w", pady=(0, 4))

        self.community_intro = ttk.Label(
            self.page,
            text=(
                "Additional thanks to xeSM3 testers/contributors and members of the Spider-Man modding community."
            ),
            style="Muted.TLabel",
            justify="left",
        )
        self.community_intro.grid(row=9, column=0, sticky="ew", pady=(0, 8))

        self.community_credits = ttk.Frame(self.page, style="Body.TFrame")
        self.community_credits.grid(row=10, column=0, sticky="ew")

        for name, role, filename in self.COMMUNITY_PEOPLE:
            card = ttk.Frame(self.community_credits, style="Panel.TFrame", padding=10)
            card.columnconfigure(0, weight=1)
            image_path = paths.ABOUT_CREDIT_IMAGES_DIR / filename
            avatar = self._load_image(name, image_path)
            if avatar is not None:
                ttk.Label(card, image=avatar, style="Panel.TLabel").grid(row=0, column=0, pady=(0, 7))
            else:
                ttk.Label(
                    card,
                    text=name[:2].upper(),
                    style="Panel.TLabel",
                    font=("Segoe UI", 22, "bold"),
                ).grid(row=0, column=0, pady=(24, 31))

            ttk.Label(
                card,
                text=name,
                style="Panel.TLabel",
                font=("Segoe UI", 11, "bold"),
                anchor="center",
            ).grid(row=1, column=0, sticky="ew")
            role_label = ttk.Label(
                card,
                text=role,
                style="Panel.TLabel",
                font=("Segoe UI", 9),
                justify="center",
                anchor="center",
            )
            role_label.grid(row=2, column=0, sticky="ew", pady=(4, 0))
            self._community_cards.append((card, role_label))

        ttk.Separator(self.page, orient="horizontal").grid(row=11, column=0, sticky="ew", pady=(16, 10))
        ttk.Label(self.page, text="RELEASE INFORMATION", style="SectionTitle.TLabel").grid(
            row=12, column=0, sticky="w", pady=(0, 4)
        )
        self.info_label = ttk.Label(
            self.page,
            text="",
            style="Muted.TLabel",
            justify="left",
            anchor="nw",
        )
        self.info_label.grid(row=13, column=0, sticky="ew", pady=(0, 8))

        self.page.bind("<Configure>", self._sync_scrollregion, add="+")
        self.page_canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        self._bind_mousewheel_tree(self.page)

        if self.app_state:
            self.app_state.on_language_change(self._apply_language)
            self.app_state.on_theme_change(lambda _theme: self._on_theme_changed())
        else:
            self._apply_language("English")

        self.after_idle(self._sync_scrollregion)

    def _bind_mousewheel_tree(self, widget) -> None:
        """Bind wheel scrolling only inside this About page; do not touch global bindings."""
        try:
            widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._bind_mousewheel_tree(child)
        except Exception:
            pass

    def _on_mousewheel(self, event) -> str:
        try:
            delta = int(-1 * (event.delta / 120))
            if delta:
                self.page_canvas.yview_scroll(delta, "units")
        except Exception:
            pass
        return "break"

    def _sync_scrollregion(self, _event=None) -> None:
        try:
            self.page_canvas.configure(scrollregion=self.page_canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, event=None) -> None:
        width = event.width if event is not None else self.page_canvas.winfo_width()
        try:
            self.page_canvas.itemconfigure(self._canvas_window, width=max(1, width))
        except Exception:
            pass

        content_width = max(320, width - 48)
        self.subtitle_label.configure(wraplength=max(260, content_width - 190))
        self.credit_intro.configure(wraplength=max(300, content_width - 10))
        self.community_intro.configure(wraplength=max(300, content_width - 10))
        self.info_label.configure(wraplength=max(300, content_width - 10))
        self._layout_wos_spotlight(content_width)
        self._layout_credit_cards(content_width)
        self._layout_community_cards(content_width)
        self._sync_scrollregion()

    def _layout_wos_spotlight(self, content_width: int) -> None:
        stacked = content_width < 760
        text_wrap = max(250, content_width - (400 if not stacked else 30))
        self.wos_shoutout_label.configure(wraplength=text_wrap)

        if stacked == self._wos_stacked:
            return
        self._wos_stacked = stacked

        self.wos_banner_label.grid_forget()
        self.wos_copy.grid_forget()
        for col in range(2):
            self.wos_spotlight.columnconfigure(col, weight=0)

        if stacked:
            self.wos_spotlight.columnconfigure(0, weight=1)
            self.wos_banner_label.grid(row=0, column=0, sticky="n", pady=(0, 10))
            self.wos_copy.grid(row=1, column=0, sticky="ew")
        else:
            self.wos_spotlight.columnconfigure(1, weight=1)
            self.wos_banner_label.grid(row=0, column=0, sticky="nw", padx=(0, 16))
            self.wos_copy.grid(row=0, column=1, sticky="nsew")

    def _layout_credit_cards(self, content_width: int) -> None:
        if content_width < 650:
            columns = 1
        elif content_width < 930:
            columns = 2
        else:
            columns = 3
        if columns == self._credit_columns:
            card_width = max(180, int(content_width / columns) - 20)
            for _card, role_label in self._credit_cards:
                role_label.configure(wraplength=max(150, card_width - 34))
            return

        self._credit_columns = columns
        for col in range(3):
            self.credits.columnconfigure(col, weight=0)
        for col in range(columns):
            self.credits.columnconfigure(col, weight=1, uniform="about_credit")

        card_width = max(180, int(content_width / columns) - 20)
        for index, (card, role_label) in enumerate(self._credit_cards):
            row, col = divmod(index, columns)
            card.grid_forget()
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            role_label.configure(wraplength=max(150, card_width - 34))

    def _layout_community_cards(self, content_width: int) -> None:
        if content_width < 650:
            columns = 1
        elif content_width < 930:
            columns = 2
        else:
            columns = 3
        if columns == self._community_columns:
            card_width = max(180, int(content_width / columns) - 20)
            for _card, role_label in self._community_cards:
                role_label.configure(wraplength=max(150, card_width - 34))
            return

        self._community_columns = columns
        for col in range(3):
            self.community_credits.columnconfigure(col, weight=0)
        for col in range(columns):
            self.community_credits.columnconfigure(col, weight=1, uniform="about_community_credit")

        card_width = max(180, int(content_width / columns) - 20)
        for index, (card, role_label) in enumerate(self._community_cards):
            row, col = divmod(index, columns)
            card.grid_forget()
            card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            role_label.configure(wraplength=max(150, card_width - 34))

    def _on_theme_changed(self) -> None:
        try:
            self.page_canvas.configure(bg=COLORS.get("bg", "#171717"))
        except Exception:
            pass

    def _apply_language(self, language: str) -> None:
        self.subtitle_label.configure(text=tr(language, "about_subtitle"))
        self.info_label.configure(text=tr(language, "about_body"))
        self.after_idle(self._sync_scrollregion)
