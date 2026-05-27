"""Shared Tk dialog for the KiriKiri Step 9 font patch workflow."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Optional, Sequence

from CherryAI.functions.kirikiri_font_patch import FontBundleSpec, FontPatchSelection


class KiriKiriFontPatchDialog(tk.Toplevel):
    def __init__(
        self,
        parent: Optional[tk.Misc],
        bundles: Sequence[FontBundleSpec],
        default_selection: FontPatchSelection,
        *,
        current_selection: Optional[FontPatchSelection],
    ) -> None:
        owner = parent.winfo_toplevel() if parent is not None else tk._get_default_root()
        super().__init__(owner)
        self._bundles = {bundle.bundle_id: bundle for bundle in bundles}
        self._bundle_order = [bundle.bundle_id for bundle in bundles]
        self.result: Optional[FontPatchSelection] = None
        self._current_selection = current_selection

        self.title("KiriKiri Font Patch")
        self.transient(owner)
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._bundle_var = tk.StringVar(value=default_selection.bundle_id)
        self._height_var = tk.IntVar(value=default_selection.height_percent)
        self._height_offset_var = tk.IntVar(value=default_selection.height_offset_pixels)
        self._charset_var = tk.IntVar(value=default_selection.charset)
        self._quality_var = tk.IntVar(value=default_selection.quality)
        self._width_var = tk.IntVar(value=default_selection.width_percent)
        self._replace_cjk_var = tk.BooleanVar(value=default_selection.replace_cjk_faces)
        self._log_var = tk.BooleanVar(value=default_selection.log_font_calls)

        self._build_ui()
        self._refresh_preview()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Stage a private-font KiriKiri version.dll patch",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=(
                "This writes version.dll at the translated root, a JSON config into "
                "the translated root, and only the selected fonts into the sibling "
                "fonts/ folder."
            ),
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(6, 10))

        form = ttk.Frame(container)
        form.pack(fill="x")

        ttk.Label(form, text="Font family:").grid(row=0, column=0, sticky="w", pady=2)
        bundle_box = ttk.Combobox(
            form,
            state="readonly",
            values=[self._bundles[bundle_id].display_name for bundle_id in self._bundle_order],
            width=28,
        )
        bundle_box.grid(row=0, column=1, sticky="ew", pady=2)
        bundle_box.current(self._bundle_order.index(self._bundle_var.get()))
        bundle_box.bind("<<ComboboxSelected>>", self._on_bundle_change)
        self._bundle_box = bundle_box

        ttk.Label(form, text="Height percent:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(form, from_=70, to=140, textvariable=self._height_var, width=8).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(form, text="Line spacing px:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Spinbox(form, from_=-10, to=10, textvariable=self._height_offset_var, width=8).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(form, text="Charset:").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Spinbox(form, from_=0, to=255, textvariable=self._charset_var, width=8).grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(form, text="Quality:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Spinbox(form, from_=0, to=6, textvariable=self._quality_var, width=8).grid(row=4, column=1, sticky="w", pady=2)

        ttk.Label(form, text="Width percent:").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Spinbox(form, from_=60, to=140, textvariable=self._width_var, width=8).grid(row=5, column=1, sticky="w", pady=2)

        ttk.Checkbutton(
            form,
            text="Replace Japanese UI faces too",
            variable=self._replace_cjk_var,
        ).grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 0),
        )
        ttk.Checkbutton(
            form,
            text="Log font calls to kirikiri-patched.log",
            variable=self._log_var,
        ).grid(
            row=7,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 0),
        )
        form.columnconfigure(1, weight=1)

        preview_frame = ttk.LabelFrame(container, text="Preview", padding=10)
        preview_frame.pack(fill="x", pady=(12, 0))
        self._current_label = ttk.Label(preview_frame, text="Current: no staged font patch")
        self._current_label.pack(anchor="w")
        self._chosen_label = ttk.Label(preview_frame, text="")
        self._chosen_label.pack(anchor="w", pady=(8, 0))
        self._sample_label = ttk.Label(
            preview_frame,
            text="The quick brown fox jumps over 1234567890 / 人類社会のすべての構成員",
        )
        self._sample_label.pack(anchor="w", pady=(4, 0))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right")
        ttk.Button(buttons, text="Stage Font Patch", command=self._accept).pack(side="right", padx=(0, 8))

    def _selected_bundle(self) -> FontBundleSpec:
        return self._bundles[self._bundle_var.get()]

    def _bundle_companion_label(self, bundle: FontBundleSpec) -> str:
        if bundle.default_latin_bundle_id is None:
            return ""
        companion = self._bundles.get(bundle.default_latin_bundle_id)
        companion_name = (
            companion.display_name if companion is not None else bundle.default_latin_bundle_id
        )
        return f" + automatic Latin companion ({companion_name})"

    def _on_bundle_change(self, _event: object) -> None:
        index = self._bundle_box.current()
        if index < 0:
            return
        self._bundle_var.set(self._bundle_order[index])
        bundle = self._selected_bundle()
        self._replace_cjk_var.set(bundle.default_replace_cjk_faces)
        self._charset_var.set(bundle.default_charset)
        self._width_var.set(bundle.default_width_percent)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self._current_selection is None:
            self._current_label.configure(text="Current: no staged font patch")
        else:
            current_bundle = self._bundles.get(self._current_selection.bundle_id)
            current_name = current_bundle.display_name if current_bundle is not None else self._current_selection.bundle_id
            self._current_label.configure(text=f"Current: {current_name}")

        bundle = self._selected_bundle()
        self._chosen_label.configure(
            text=(
                f"Chosen: {bundle.display_name}{self._bundle_companion_label(bundle)} "
                f"({bundle.regular_file}, {bundle.bold_file or 'no bold companion'})"
            )
        )
        families = {name.lower() for name in tkfont.families(self)}
        preview_font = (bundle.face_name, 12)
        preview_suffix = "preview available"
        if bundle.face_name.lower() not in families:
            preview_font = ("TkDefaultFont", 10)
            preview_suffix = "preview unavailable on this system"
        self._sample_label.configure(
            font=preview_font,
            text=(
                f"{bundle.face_name}: The quick brown fox jumps over 1234567890 / "
                f"人類社会のすべての構成員 ({preview_suffix})"
            ),
        )

    def _accept(self) -> None:
        bundle = self._selected_bundle()
        self.result = FontPatchSelection(
            bundle_id=bundle.bundle_id,
            regular_file=bundle.regular_file,
            bold_file=bundle.bold_file,
            match_faces=bundle.default_match_faces,
            height_percent=self._height_var.get(),
            height_offset_pixels=self._height_offset_var.get(),
            width_percent=self._width_var.get(),
            replace_cjk_faces=self._replace_cjk_var.get(),
            charset=self._charset_var.get(),
            quality=self._quality_var.get(),
            log_font_calls=self._log_var.get(),
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def choose_kirikiri_font_patch_selection(
    parent: Optional[tk.Misc],
    bundles: Sequence[FontBundleSpec],
    default_selection: FontPatchSelection,
    *,
    current_selection: Optional[FontPatchSelection],
) -> Optional[FontPatchSelection]:
    dialog = KiriKiriFontPatchDialog(
        parent,
        bundles,
        default_selection,
        current_selection=current_selection,
    )
    dialog.wait_window()
    return dialog.result