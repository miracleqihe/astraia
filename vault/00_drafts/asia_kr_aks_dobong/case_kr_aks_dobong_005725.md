---
id: case_kr_aks_dobong_005725
title: 韩国口碑目录 · 망짝으로 곰잡기
aliases:
- 망짝으로 곰잡기
node_type: case
z_layer: 1
genre: unclassified
credibility_tier: B
is_fictional_quarantine: false
spatial:
  lat: null
  lng: null
  precision: culture_region
  location_name: 韩国首尔道峰区（目录采录范围；叙事地点待核）
  culture_region: East Asia · Korea
temporal: null
standards:
  atu_types: []
  thompson_motifs: []
  berezkin_codes: []
  ocm_codes: []
  macro_phylogeny: null
mechanisms: []
relations:
- type: PART_OF_MACRO_TREND
  target: corpus_kr_aks_dobong
  weight: 1.0
  note: 同一开放目录筛查范围，不表示同一故事或传播关系。
  status: null
sources:
- citation: 韩国公共数据门户，韩国学中央研究院声音资料目录原始压缩包。
  type: korea_aks_catalogue
  url: https://www.data.go.kr/data/15070383/fileData.do
  doi: null
  locator: 한국구비문학대계(1).csv / 数据行 5725
  local_path: .local/import-sources/korea-aks-audio-index-2026-11-22.zip
  content_sha256: d600398e3da896acaa388d190efebc6fd8392c3cb2b51e293895d71bbf369d68
- citation: 项目下载凭据；目录文件许可与音视频、正文许可分别核对。
  type: korea_aks_receipt
  url: https://www.data.go.kr/data/15070383/fileData.do
  doi: null
  locator: 目录下载凭据
  local_path: .local/import-sources/korea-aks-audio-index-2026-11-22.receipt.json
  content_sha256: 87b107d2f1237d51af9614ef375826804261c55a50209b0c5ed168a31454d1a6
- citation: 馆方检索字段索引清单；未保存网页原响应。
  type: korea_aks_search_manifest
  url: https://kdp.aks.ac.kr/inde/search?itemId=14&pageIndex=1&pageUnit=20
  doi: null
  locator: 道峰区检索字段索引
  local_path: .local/import-sources/korea-aks-kdp-dobong-2026-11-23-v1/manifest.json
  content_sha256: 00892974cb6e5624ff7542124a3f005e599e279d20e2b397e5022e8051ba3436
- citation: 馆方单条详情字段索引清单；未复制正文或音视频。
  type: korea_aks_detail_manifest
  url: https://kdp.aks.ac.kr/inde/search?itemId=14&pageIndex=1&pageUnit=20
  doi: null
  locator: 候选详情字段索引
  local_path: .local/import-sources/korea-aks-kdp-dobong-details-2026-11-23-v1/manifest.json
  content_sha256: bbe02f8e76de8fd22383ac4188a5b6259cfdf8a8cce20b20e87fd3d8baddcb60
- citation: 项目来源候选基础对照；匹配仅供人工复核。
  type: korea_aks_crosswalk_base
  url: https://kdp.aks.ac.kr/inde/search?itemId=14&pageIndex=1&pageUnit=20
  doi: null
  locator: 道峰区来源候选
  local_path: reference/korea_aks_dobong_crosswalk_2026-11-23.csv
  content_sha256: 07d18357cfadfffc20d680db07cfb07f187555a8adf9d22abad92aee9f81148e
- citation: 项目来源候选及详情字段对照；响应指纹不能离线重算。
  type: korea_aks_crosswalk_detail
  url: https://kdp.aks.ac.kr/inde/search?itemId=14&pageIndex=1&pageUnit=20
  doi: null
  locator: 道峰区详情对照
  local_path: reference/korea_aks_dobong_detail_review_2026-11-23.csv
  content_sha256: 698263e776654508ffdc75f85108d15d26ddd6a82e5b348c1848f8a5927d4f33
- citation: AKS 馆方检索字段索引；原网页未保存，响应指纹不可离线重算。
  type: korea_aks_search_index
  url: https://kdp.aks.ac.kr/inde/search?itemId=14&pageIndex=7&pageUnit=20
  doi: null
  locator: POKS.GUBI.GUBI.1_5717
  local_path: .local/import-sources/korea-aks-kdp-dobong-2026-11-23-v1/page-07.json
  content_sha256: d7005ec555acbf25c8438cc0d068fa8e32a35eb9fcbf265e47a1bcaa64a0edeb
- citation: AKS 馆方单条元数据字段索引；原文和音视频请在馆方页面查看。
  type: korea_aks_detail_index
  url: https://kdp.aks.ac.kr/inde/gubi?id=POKS.GUBI.GUBI.1_5717
  doi: null
  locator: POKS.GUBI.GUBI.1_5717
  local_path: .local/import-sources/korea-aks-kdp-dobong-details-2026-11-23-v1/records/POKS.GUBI.GUBI.1_5717.json
  content_sha256: a15aef581ef5fcf444f8a69ccbf70c18825f3176dfc8e32a592911a1e2db1653
audit:
  created_at: '2026-11-22'
  reviewed_by_human: false
  ai_confidence: null
  is_sample: false
  reviewer: null
  reviewed_at: null
  review_note: null
---

## 馆方目录及来源候选

```
{
  "目录数据行序号": 5725,
  "目录字段": {
    "서명": "망짝으로 곰잡기",
    "구연자": "김용규",
    "채록지": "서울시-도봉구-도봉구 수유2동",
    "유형": "설화",
    "텍스트": "tsu_0017"
  },
  "馆方候选": [
    {
      "馆方编号": "POKS.GUBI.GUBI.1_5717",
      "馆方检索题名": "망짝으로 곰 잡기",
      "馆方讲述者": "김용규",
      "馆方检索类别": "설화",
      "馆方检索区域": "서울 / 도봉구",
      "馆方调查日期（非叙事年代）": "1979.05.13",
      "馆方调查者": "조희웅, 이영성, 양혜정",
      "题名对照方式": "规范化一致",
      "题名相似度": "1.000",
      "该馆方记录的目录候选数": "1",
      "候选单条页面": "https://kdp.aks.ac.kr/inde/gubi?id=POKS.GUBI.GUBI.1_5717",
      "馆方详情题名": "망짝으로 곰 잡기",
      "馆方详情讲述者": "김용규",
      "馆方详情类别": "설화",
      "馆方详情采录地点": "서울시 도봉구 수유2동",
      "馆方详情调查日期（非叙事年代）": "1979.05.13",
      "馆方详情调查者": "조희웅, 이영성, 양혜정",
      "馆方详情地区": "서울",
      "检索与详情题名": "一致",
      "检索与详情讲述者": "一致",
      "检索与详情类别": "一致",
      "检索与详情日期": "一致",
      "目录与详情采录地点": "一致",
      "详情字段索引SHA256": "a15aef581ef5fcf444f8a69ccbf70c18825f3176dfc8e32a592911a1e2db1653",
      "详情网页响应SHA256": "b295ff324965a7a47aa76142c0d98b1c7cad330b9b44a331da75b7fb64b1e509",
      "待核问题": "候选由题名、讲述者、馆方类别和道峰区范围生成，均须人工核对；采录地点与日期不等于故事发生时空；坐标和标准码待核；单条详情字段已采集；同一次演述、日期与版本仍须人工核对；两处题名原字段不同"
    }
  ],
  "候选数": 1,
  "范围说明": "候选来自道峰区检索字段；录音或目录行不等于独立故事，短编号不是标准码。"
}
```

## 原文与复核

本卡保留原目录字段及待核来源候选，未保存转写正文或音视频；可通过候选来源链接查看馆方单条页面。题名相似、讲述者和采录区域对应仍不证明同一次演述。馆方调查日期与采录地点不自动成为故事发生时空；具体版本、许可及相关社区要求须逐项核对。目录文本短编号不是国际标准码，标准码仅可从本地码表核定。
