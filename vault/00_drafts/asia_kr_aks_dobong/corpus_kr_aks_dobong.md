---
id: corpus_kr_aks_dobong
title: 韩国首尔道峰区口碑目录 · AKS
aliases: []
node_type: myth_corpus
z_layer: 2
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
relations: []
sources:
- citation: 韩国公共数据门户，韩国学中央研究院声音资料目录原始压缩包。
  type: korea_aks_catalogue
  url: https://www.data.go.kr/data/15070383/fileData.do
  doi: null
  locator: 口碑文学目录 / 道峰区筛查
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
audit:
  created_at: '2026-11-22'
  reviewed_by_human: false
  ai_confidence: null
  is_sample: false
  reviewer: null
  reviewed_at: null
  review_note: null
---

## 馆藏与核查范围

开放目录中 172 行的采录地字段属于首尔道峰区；馆方检索页列出 202 条记录。114 行得到来源候选，58 行暂未找到；候选来源共 113 条已保存单条元数据字段。这些是目录与检索行数，不是独立故事数；候选不证明同一次演述。未保存音视频、转写或馆方网页原响应，网页响应指纹不能单凭字段索引离线重算。单条许可、版本、体裁和相关社区要求须人工核对；坐标、叙事年代和标准码留空。
