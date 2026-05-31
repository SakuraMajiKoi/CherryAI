import json
from pathlib import Path

from formats.rpgmakermvmz import RpgMakerMZHandler, RpgMakerPluginHandler


def test_mvmz_sample_workflow_json_syntax_roundtrips(tmp_path: Path) -> None:
    """Coverage for representative branches from dev/samples/mvmzworkflow.py."""
    path = tmp_path / "MapSample.json"
    data = {
        "events": [
            None,
            {
                "name": "イベント名",
                "pages": [
                    {
                        "list": [
                            {"code": 101, "parameters": ["", 0, 0, 2, "村人"]},
                            {"code": 401, "parameters": ["こんにちは"]},
                            {"code": 401, "parameters": ["世界"]},
                            {"code": 0, "parameters": []},
                            {"code": 401, "parameters": ["【案内人】同じ行の台詞"]},
                            {"code": 405, "parameters": ["スクロール一"]},
                            {"code": 405, "parameters": ["スクロール二"]},
                            {"code": 408, "parameters": ["注釈一"]},
                            {"code": 408, "parameters": ["注釈二"]},
                            {"code": 102, "parameters": [["選択一", "if($gameSwitches.value(1))選択二"], 0, 0, 2, 0]},
                            {"code": 122, "parameters": [1, 1, 0, 0, "`変数テキスト`"]},
                            {"code": 320, "parameters": [1, "改名"]},
                            {"code": 324, "parameters": [1, "異名"]},
                            {"code": 325, "parameters": [1, "プロフィール文"]},
                            {"code": 108, "parameters": ["info:情報文, meta"]},
                            {"code": 108, "parameters": ["<ActiveMessage:アクティブ文>"]},
                            {"code": 356, "parameters": ["D_TEXT コマンド文 12"]},
                            {"code": 356, "parameters": ["ShowInfo お知らせ文"]},
                            {"code": 356, "parameters": ["LL_GalgeChoiceWindowMV setChoices はい,いいえ"]},
                            {"code": 355, "parameters": ["テキスト-スクリプト文"]},
                            {"code": 355, "parameters": ["var text1 = \"変数スクリプト\""]},
                            {"code": 355, "parameters": ["$gameVariables.setValue(2, \"代入文\")"]},
                            {"code": 355, "parameters": ["BattleManager._logWindow.addText(\"戦闘ログ\");"]},
                            {"code": 655, "parameters": ["BattleManager._logWindow.push('addText', '追加ログ')"]},
                            {"code": 357, "parameters": ["QuestSystem", "Show", 0, {"DetailNote": "クエスト詳細"}]},
                            {
                                "code": 357,
                                "parameters": [
                                    "VisuMZ_4_ProximityMessages",
                                    "Show",
                                    0,
                                    {"Text:json": '"\\\\{\\\\{近接メッセージ\\\\}\\\\}"'},
                                ],
                            },
                            {"code": 357, "parameters": ["AdvExtentionllk", "Show", 0, {"name": "話者名", "comment": "拡張コメント"}]},
                            {"code": 657, "parameters": ["'メッセージ = ピクチャ説明'"]},
                            {"code": 111, "parameters": [0, "$gameVariables.value(1) === \"条件名\""]},
                        ]
                    }
                ],
            },
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    handler = RpgMakerMZHandler()
    tagged = handler.extract_tagged(path)
    actual = {(line.tag, line.text) for line in tagged}

    expected = {
        ("name", "イベント名"),
        ("401", "村人: こんにちは\n世界"),
        ("401", "案内人: 同じ行の台詞"),
        ("405", "スクロール一\nスクロール二"),
        ("408", "注釈一\n注釈二"),
        ("102", "選択一"),
        ("102", "if($gameSwitches.value(1))選択二"),
        ("122", "変数テキスト"),
        ("320", "改名"),
        ("324", "異名"),
        ("325", "プロフィール文"),
        ("108", "情報文"),
        ("108", "アクティブ文"),
        ("dtext", "コマンド文"),
        ("showinfo", "お知らせ文"),
        ("galge", "はい"),
        ("galge", "いいえ"),
        ("テキスト", "スクリプト文"),
        ("vartext", "変数スクリプト"),
        ("gamevariables", "代入文"),
        ("battlelog", "戦闘ログ"),
        ("battlelog", "追加ログ"),
        ("questsystem", "クエスト詳細"),
        ("visumz", "近接メッセージ"),
        ("advextentionllk", "話者名"),
        ("advextentionllk", "拡張コメント"),
        ("657", "ピクチャ説明"),
        ("111", "条件名"),
    }
    assert expected <= actual
    assert all(line.tag for line in tagged)

    translations = []
    for index, line in enumerate(tagged):
        if line.text == "村人: こんにちは\n世界":
            translations.append("Villager: Hello\nWorld")
        elif line.text == "案内人: 同じ行の台詞":
            translations.append("Guide: Inline speech")
        else:
            translations.append(f"TL{index}")

    handler.inject(path, translations)
    rendered = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False)

    assert "Villager" in rendered
    assert "Guide" in rendered
    assert "こんにちは" not in rendered
    assert "クエスト詳細" not in rendered
    assert "近接メッセージ" not in rendered
    assert "条件名" not in rendered


def test_mvmz_sample_database_note_syntax_roundtrips(tmp_path: Path) -> None:
    """Coverage for note/name fields from dev/samples/mvmzworkflow.py."""
    path = tmp_path / "Items.json"
    data = [
        None,
        {
            "id": 1,
            "name": "薬草",
            "description": "体力を回復する",
            "note": (
                "<note:短いノート>\n"
                "<Hint:ヒント文>\n"
                "<SG説明:\n説明一>\n"
                "<MapText:地図文>\n"
                "<ClassMessage>\nクラス文</ClassMessage>"
            ),
        },
    ]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    handler = RpgMakerMZHandler()
    tagged = handler.extract_tagged(path)
    actual = {(line.tag, line.text) for line in tagged}

    assert {
        ("name", "薬草"),
        ("description", "体力を回復する"),
        ("note", "短いノート"),
        ("hint", "ヒント文"),
        ("sg", "説明一"),
        ("maptext", "地図文"),
        ("classmessage", "クラス文"),
    } <= actual

    handler.inject(path, [f"DB{i}" for i, _line in enumerate(tagged)])
    rendered = path.read_text(encoding="utf-8")
    assert "薬草" not in rendered
    assert "短いノート" not in rendered
    assert "クラス文" not in rendered


def test_plugin_sample_js_regex_syntax_roundtrips(tmp_path: Path) -> None:
    """Coverage for regex branches in dev/samples/plugins.py."""
    path = tmp_path / "QuestSceneMenu.js"
    path.write_text(
        "\n".join(
            [
                "/*:",
                " * @text プラグイン表示名",
                " * @desc プラグイン説明",
                " */",
                'const title = { text: "タイトル文" };',
                r'const q = "{\"QuestName\":\"クエスト名\",\"QuestClientName\":\"依頼人\",\"QuestLocation\":\"場所\",\"PlaceInformation\":\"目的地\",\"QuestContent\":\"\"概要文\"\",\"ObjectiveContent\":\"\"達成条件\"\"}";',
                r'const menu = "{\"Text\":\"メニュー項目\",\"CommonHelpText\":\"共通ヘルプ\",\"HelpText\":\"ヘルプ文\",\"ParamName\":\"現在地\"}";',
                r'txtSubject = "件名";',
                r'this.drawTextEx("\\}見出し\\{ C[16]攻撃力\\C[0]", 0, 0);',
                'this.disp_list = { area: { names: ["地域名", "別地域"] } };',
            ]
        ),
        encoding="utf-8",
    )

    handler = RpgMakerPluginHandler()
    tagged = handler.extract_tagged(path)
    actual = {(line.tag, line.text) for line in tagged}

    expected = {
        ("questscenemenu_text", "プラグイン表示名"),
        ("questscenemenu_desc", "プラグイン説明"),
        ("questscenemenu", "タイトル文"),
        ("questscenemenu_questname", "クエスト名"),
        ("questscenemenu_questclient", "依頼人"),
        ("questscenemenu_questlocation", "場所"),
        ("questscenemenu_place", "目的地"),
        ("questscenemenu_questcontent", "概要文"),
        ("questscenemenu_objective", "達成条件"),
        ("questscenemenu_text", "メニュー項目"),
        ("questscenemenu_commonhelp", "共通ヘルプ"),
        ("questscenemenu_help", "ヘルプ文"),
        ("questscenemenu_param", "現在地"),
        ("questscenemenu_subject", "件名"),
        ("questscenemenu_drawlabel", "見出し"),
        ("questscenemenu_stat", "攻撃力"),
        ("questscenemenu_disp", "地域名"),
        ("questscenemenu_disp", "別地域"),
    }
    assert expected <= actual
    assert all(line.tag for line in tagged)

    handler.inject(path, [f"JS{i}" for i, _line in enumerate(tagged)])
    rendered = path.read_text(encoding="utf-8")
    assert "クエスト名" not in rendered
    assert "共通ヘルプ" not in rendered
    assert "攻撃力" not in rendered
    assert "地域名" not in rendered
