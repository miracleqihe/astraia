"""Stage EAP081/25 catalogue groups as recordings, not individual stories."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re

from pipeline.fetch_bl_yi import CC_BY, ROOT_URL, load_snapshot
from pipeline.ingest_agent import literal_block
from pipeline.lao_manuscripts import display_path
from pipeline.node_model import NodeMetadata

ROOT_ID = 'corpus_cn_bl_yi_eap081_25'
PREFIX = ROOT_ID + '_'


def duration_minutes(extent: str | None) -> int | None:
    """Only interpret an explicitly printed hours/minutes field."""
    if not extent:
        return None
    hours = re.search(r'(\d+)\s+hours?\b', extent, re.I)
    minutes = re.search(r'(\d+)\s*minutes?\b', extent, re.I)
    if not hours and not minutes:
        return None
    return (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)


def group_evidence(fields: dict, records: list) -> dict:
    durations = [duration_minutes(item[3].get('Extent')) for item in records]
    return {'馆方档号': fields.get('Reference (shelfmark)'), '馆方题名': fields.get('Title'),
            '馆方内容说明': fields.get('Scope & Content'), '馆方范围与总时长': fields.get('Extent'),
            '馆方语言字段': fields.get('Languages'), '馆方日期起始原字段': fields.get('Start Date'),
            '馆方日期结束原字段': fields.get('End Date'), '馆方日期范围原字段': fields.get('Date Range'),
            '馆方访问条件': fields.get('User Conditions'), '馆方原件保存说明': fields.get('Information About Originals'),
            '六组时长字段相加分钟数（待核）': sum(durations) if all(value is not None for value in durations) else None}


def child_evidence(fields: dict) -> dict:
    return {'馆方档号': fields.get('Reference (shelfmark)'), '馆方记录号': fields.get('Record Id'),
            '馆方题名': fields.get('Title'), '馆方内容说明': fields.get('Scope & Content'),
            '馆方文件数和时长': fields.get('Extent'), '馆方语言字段': fields.get('Languages'),
            '馆方文字字段': fields.get('Scripts'), '馆方日期起始原字段': fields.get('Start Date'),
            '馆方日期结束原字段': fields.get('End Date'), '馆方日期范围原字段': fields.get('Date Range'),
            '馆方数字内容字段': fields.get('Digitised Content'), '馆方访问条件': fields.get('User Conditions'),
            '馆方原件保存说明': fields.get('Information About Originals'), '馆方记录级别': fields.get('Record Type (Level)')}


def cards(folder: Path):
    selection, root_fields, records = load_snapshot(folder)
    root_path, manifest = folder / 'root.html', folder / 'manifest.json'
    common = {'node_type': 'myth_corpus', 'z_layer': 2, 'genre': 'unclassified', 'credibility_tier': 'B',
              'is_fictional_quarantine': False,
              'spatial': {'precision': 'culture_region', 'location_name': '云南彝语馆藏；各录音地点须逐条核对',
                          'culture_region': 'East Asia · China'},
              'temporal': None, 'standards': {}, 'audit': {'created_at': date.today(), 'reviewed_by_human': False}}
    parent = {'citation': 'British Library Archives and Manuscripts Catalogue, EAP081/25；目录文字 CC BY 4.0，录音权利另核。',
              'type': 'bl_yi_group', 'url': ROOT_URL, 'locator': 'EAP081/25 / 馆藏组',
              'local_path': display_path(root_path), 'content_sha256': selection['root_sha256']}
    receipt = {'citation': '本项目馆方目录快照清单；单条录音及社区要求另核。', 'type': 'bl_yi_manifest',
               'url': ROOT_URL, 'locator': '馆藏组与六个子组的快照清单', 'local_path': display_path(manifest),
               'content_sha256': sha256(manifest.read_bytes()).hexdigest()}
    root_data = group_evidence(root_fields, records)
    model = {**common, 'id': ROOT_ID, 'title': '云南彝语口述录音 · EAP081/25 馆藏组', 'sources': [parent, receipt]}
    body = ('\n## 馆方馆藏组字段\n\n' + literal_block(json.dumps(root_data, ensure_ascii=False, indent=2))
            + '\n\n## 复核范围\n\n馆藏按六位毕摩讲述者分为六个子组，目录列 81 个音频文件，'
              '文件数和组数均不等于故事数。馆方描述的项目年份、统一日期字段与单条录音日期应分开核对。'
              '六组所列时长之和与父级约数不同，不能自动修改；请回查馆方的计数口径。'
              '本地未取得音频或转写，目录文字 CC BY 4.0；录音限研究使用，其他使用和相关社区要求另核。\n')
    yield NodeMetadata.model_validate(model), body
    for child, path, checksum, fields in records:
        number = child['number']
        source = {'citation': 'British Library Archives and Manuscripts Catalogue, EAP081/25；目录文字 CC BY 4.0，录音权利另核。',
                  'type': 'bl_yi_child', 'url': child['url'], 'locator': f'EAP081/25/{number} / 录音子组',
                  'local_path': display_path(path), 'content_sha256': checksum}
        item = {**common, 'id': f'{PREFIX}{number:02d}', 'title': f'云南彝语口述录音 · EAP081/25/{number}',
                'aliases': [fields['Title']], 'relations': [{'type': 'PART_OF_MACRO_TREND', 'target': ROOT_ID,
                    'note': '同一馆方录音馆藏的子组，不等于单篇故事或同一叙事事件。'}],
                'sources': [source, parent, receipt]}
        data = child_evidence(fields)
        body = ('\n## 馆方录音子组字段\n\n' + literal_block(json.dumps(data, ensure_ascii=False, indent=2))
                + '\n\n## 复核范围\n\n本卡为馆方按讲述者组织的录音子组，可能包含多个文件或不同内容，'
                  '不自动判定为单篇故事。录音者、讲述者、方言、具体地点及采集日期以原字段为线索逐项复核；'
                  '馆方统一日期字段不能直接作为录音或叙事年代。目录文字 CC BY 4.0，录音限研究使用，'
                  '本地未下载音频或转写；其他许可和社区要求另核。坐标及国际标准码留空。\n')
        if number == 4:
            body += '\n题名写作 Pu Rongxiang，内容说明写作 Pu Rongziang；姓名拼写待核。\n'
        yield NodeMetadata.model_validate(item), body
