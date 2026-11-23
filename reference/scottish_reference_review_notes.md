# 苏格兰猎巫史料索引：未关联记录核查

本地爱丁堡调查库原表有 13 行 `WDB_Reference` 的 `CaseRef` 在 `WDB_Case` 中找不到。原始行、备注和档号保留在 `web/public/review/unmatched_references.csv`，不自动接入其他案件。检查使用的调查表 SHA-256 为 `cc56c499e9544dca8ac1b720ab2784769bb497717f5790db4a32b5b2b3c4cc7c`。

例如，`R/EGD/1024` 的原表案件号是 `C/EGD/1024`，而尾号相同的被告 `A/EGD/1024` 在调查库实际关联的案件是 `C/EGD/1035`。后者有自己登记的史料线索；这并不能确定未关联的 `R/EGD/1024` 应归属于哪个案件。相同数字尾号不能作为被告、案件和史料索引之间的关联依据。 [爱丁堡被告登记](https://witches.hca.ed.ac.uk/accused/A/EGD/1024) · [爱丁堡案件登记](https://witches.hca.ed.ac.uk/case/C/EGD/1035)

后续应以原始卷册、登记版本或馆藏人员提供的更正为依据，再逐项处理这些未关联行。
