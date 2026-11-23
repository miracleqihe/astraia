"""Stage the first national ICH register's folk-literature project metadata.

The register is a finding aid, not a transcript of the stories it names. Its
administrative project numbers must not be treated as folklore motif codes.
"""
from datetime import date
from hashlib import sha256
from pathlib import Path
import re

from bs4 import BeautifulSoup

from pipeline.build_graph import PROJECT_ROOT
from pipeline.intake_sources import IntakeError
from pipeline.node_model import NodeMetadata

SOURCE_URL = "https://zwgk.mct.gov.cn/zfxxgkml/fwzwhyc/202012/t20201206_916788.html"
SOURCE_TITLE = "国务院关于公布第一批国家级非物质文化遗产名录的通知（2006），一、民间文学"
ROW = re.compile(r"^\s*(\d+)\s+Ⅰ[—–-](\d+)\s+(.+?)\s{2,}(.+?)\s*$")


def register_rows(raw: bytes) -> list[dict]:
    soup = BeautifulSoup(raw, "html.parser")
    body = soup.select_one(".gsj_htmlcon_bot")
    if body is None or soup.contains_replacement_characters:
        raise IntakeError("名录页面结构或中文编码不可靠，不能生成批次。")
    lines = body.get_text("\n", strip=True).splitlines()
    if not any("第一批国家级非物质文化遗产名录" in line for line in lines):
        raise IntakeError("来源页面未标明第一批国家级非物质文化遗产名录。")
    starts = [i for i, line in enumerate(lines) if re.search(r"一、民间文学\s*[（(]共计31项[）)]", line)]
    if len(starts) != 1:
        raise IntakeError("未找到唯一的第一批民间文学名录。")
    rows, current, section_end = [], None, False
    for line in lines[starts[0] + 1:]:
        if re.match(r"^二、", line):
            section_end = True
            break
        match = ROW.fullmatch(line)
        if match:
            index, code, title, area = match.groups()
            if index != code or int(index) != len(rows) + 1:
                raise IntakeError(f"名录序号或项目号不连续：{line}")
            current = {"index": int(index), "code": f"Ⅰ—{code}", "title": title.strip(),
                       "area_lines": [area.strip()], "raw_lines": [line]}
            rows.append(current)
        elif current and line.strip():
            current["area_lines"].append(line.strip())
            current["raw_lines"].append(line)
    if not section_end:
        raise IntakeError("未找到民间文学名录的结束边界。")
    if len(rows) != 31:
        raise IntakeError(f"第一批民间文学应有 31 项，实际识别到 {len(rows)} 项。")
    if rows[0]["title"] != "苗族古歌" or rows[-1]["title"] != "青林寺谜语":
        raise IntakeError("名录首尾项目与第一批民间文学不符，请核对来源。")
    return rows


def heritage_cards(path: Path):
    path = path.resolve(strict=True)
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    try:
        local_path = path.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        local_path = str(path)
    for row in register_rows(raw):
        region = "\n".join(row["area_lines"])
        data = {
            "id": f"corpus_cn_ich_2006_{row['index']:02d}",
            "title": f"国家级非遗名录 · {row['title']}",
            "aliases": [f"非遗项目 {row['code']}"],
            "node_type": "myth_corpus", "z_layer": 2,
            "genre": "unclassified", "credibility_tier": "B", "is_fictional_quarantine": False,
            "spatial": {"precision": "culture_region", "location_name": f"2006 年申报地区或单位（按原文换行）：{region}",
                        "culture_region": "East Asia · China"},
            "temporal": None, "standards": {},
            "sources": [{"citation": SOURCE_TITLE, "type": "heritage_register", "url": SOURCE_URL,
                         "locator": f"一、民间文学 / 序号 {row['index']} / 项目编号 {row['code']}",
                         "local_path": local_path, "content_sha256": digest}],
            "audit": {"created_at": date.today(), "reviewed_by_human": False},
        }
        excerpt = "\n".join(row["raw_lines"])
        body = ("\n## 名录原文\n\n```text\n" + excerpt + "\n```\n\n"
                "## 复核说明\n\n此卡是 2006 年公布的名录项目及申报地区或单位，不是单篇采录原文。"
                "原文换行及当时的名称保留；行政名称可能已经变化。申报地不等于故事发生地或采录地，"
                "坐标留空。项目编号是非遗登记号，不是 ATU、汤普森、别列兹金或 OCM 标准码。"
                "请核对具体版本、传承人和采录出处后再确定体裁及标引。\n")
        yield NodeMetadata.model_validate(data), body
