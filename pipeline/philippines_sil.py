"""Stage SIL Philippines' two public Ilianen Manobo recording descriptions.

The local source is the catalogue HTML only: no audio or transcription is copied.
"""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from pipeline.ingest_agent import literal_block
from pipeline.intake_sources import IntakeError, _challenge_page, one_line
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

SOURCE_URL = "https://philippines.sil.org/resources/audio_and_video/ilianen_manobo_oral_narrative_recordings"
ROOT_ID = "corpus_ph_ilianen_sil"
ENTRIES = (
    ("case_ph_ilianen_pilanduk", "Si Pilanduk wey ke Datu te Buaya", "Pilanduk and the Crocodile Chief",
     "The Song from the Mango Tree", "Hazel Wrigglesworth and Ampatuan Ampalid 2004"),
    ("case_ph_ilianen_tulalang", "Ke Kenakan ne Mevantug ne Midrirunrirung ne Mibpebaluy ne Pilas ne Uval",
     "The Famous Young-man Who Disguised Himself as a Monkey", "Narrative Episodes from the Tulalang Epic",
     "Hazel J. Wrigglesworth, Ampatuan Ampalid, Letipá Andaguer and Adriano Ambangan 2008"),
)


def parse_catalogue(path: Path) -> dict[str, dict]:
    raw = path.read_bytes()
    soup = BeautifulSoup(raw, "html.parser", from_encoding="utf-8")
    text = one_line(soup.get_text(" ", strip=True))
    if (soup.contains_replacement_characters or _challenge_page(soup)
            or "Ilianen Manobo Oral Narrative Recordings" not in text
            or "samples from two of the narratives of Ampatuan Ampalid" not in text
            or "complete digitized recordings onsite" not in text):
        raise IntakeError("SIL 页面标题、样本范围或现场访问说明不符。")
    result = {}
    for node_id, expected_title, expected_english, expected_book, expected_credit in ENTRIES:
        matches = [tag for tag in soup.find_all("em") if one_line(tag.get_text(" ", strip=True)) == expected_title]
        if len(matches) != 1:
            raise IntakeError(f"SIL 样本题名缺失或重复：{expected_title}")
        title_item = matches[0].find_parent("li")
        item = title_item.find_next_sibling("li") if title_item else None
        if not item:
            raise IntakeError(f"SIL 样本说明缺失：{expected_title}")
        direct = " ".join(one_line(str(child)) for child in item.children if isinstance(child, str)).strip()
        item_text = one_line(item.get_text(" ", strip=True))
        book = next((a for a in item.find_all("a") if one_line(a.get_text(" ", strip=True)) == expected_book), None)
        audio = title_item.find("a", href=True)
        if (direct != expected_english or "by Ampatuan Ampalid" not in item_text
                or not re.search(r"Recorded:\s*August 2, 1976", item_text)
                or "Oral transcription published in" not in item_text or expected_credit not in item_text
                or not book or not audio):
            raise IntakeError(f"SIL 样本的讲述者、录音日期或书目说明不符：{expected_title}")
        book_url, audio_url = book.get("href", ""), audio.get("href", "")
        for url in (book_url, audio_url):
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.netloc != "philippines.sil.org" or parts.query or parts.fragment:
                raise IntakeError("SIL 样本链接指向了未登记的域名。")
        if not urlsplit(audio_url).path.lower().endswith(".mp3"):
            raise IntakeError("SIL 样本音频链接格式不符。")
        result[node_id] = {"馆方题名": expected_title, "馆方英文题名": direct, "讲述人": "Ampatuan Ampalid",
                           "馆方录音日期": "1976-08-02", "馆方提及的转写本": expected_book,
                           "转写本署名及年份（馆方原字段）": expected_credit, "转写本介绍链接": book_url,
                           "在线样本链接": audio_url, "完整录音访问": "馆方说明须申请在马尼拉档案现场收听",
                           "具体录音地点": None, "文本与音频再利用许可": "待核"}
    return result


def ilianen_cards(path: Path):
    items = parse_catalogue(path)
    digest = sha256(path.read_bytes()).hexdigest()
    common = {"genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
              "spatial": {"precision": "culture_region", "location_name": "菲律宾（资料主题范围；具体录音地点未明）",
                          "culture_region": "Southeast Asia · Philippines"},
              "temporal": None, "standards": {}, "audit": {"created_at": date.today(), "reviewed_by_human": False}}

    def source(locator: str) -> dict:
        return {"citation": "SIL Philippines，Ilianen Manobo Oral Narrative Recordings，在线样本及馆藏说明。",
                "type": "sil_ilianen_catalogue", "url": SOURCE_URL, "locator": locator,
                "local_path": display_path(path), "content_sha256": digest}

    root = {**common, "id": ROOT_ID, "title": "菲律宾 Ilianen Manobo 口述录音 · SIL 样本",
            "node_type": "myth_corpus", "z_layer": 2, "sources": [source("录音样本及现场访问说明")]}
    root_body = ("\n## 馆藏范围\n\nSIL 页面提供 Ampatuan Ampalid 讲述的两则录音样本。"
                 "馆方说明完整数字录音需申请在马尼拉档案现场收听，并注明两本相关转写出版物；"
                 "本地只保存网页目录，没有复制录音或转写正文。具体录音地点和音频、文本再利用许可待核。"
                 "研究者曾在北哥打巴托居住的背景不证明这两次录音的具体地点，录音日期也不是故事发生年代。\n")
    yield NodeMetadata.model_validate(root), root_body
    for node_id, *_ in ENTRIES:
        item = items[node_id]
        model = {**common, "id": node_id, "title": f"菲律宾口述录音 · {item['馆方题名']}",
                 "aliases": [item["馆方题名"], item["馆方英文题名"]], "node_type": "case", "z_layer": 1,
                 "relations": [{"type": "PART_OF_MACRO_TREND", "target": ROOT_ID,
                                "note": "同一馆藏页面的口述录音样本；不表示采录地点或传播路径相同。"}],
                 "sources": [source(item["馆方题名"])]}
        body = ("\n## 馆方目录字段\n\n" + literal_block(json.dumps(item, ensure_ascii=False, indent=2))
                + "\n\n## 原文、录音与复核\n\n页面提供录音样本，完整录音须按馆方说明申请现场收听；"
                  "所列印刷转写本尚未查阅，不能据目录推定其具体页码或与样本完全相同。"
                  "采录者角色、录音地点、语言、体裁及与相关社区的使用条件须核对；"
                  "叙事发生时间、坐标和标准码未自动推定。\n")
        yield NodeMetadata.model_validate(model), body
