import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { registerHooks } from 'node:module';
import { test } from 'node:test';

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === './graph' && context.parentURL?.endsWith('/catalogueBrowse.ts')) {
      return nextResolve('./graph.ts', context);
    }
    return nextResolve(specifier, context);
  },
});

const { REGIONS, nodeRegion } = await import('../src/catalogueBrowse.ts');

const readJson = async (relativePath) => JSON.parse(await readFile(new URL(relativePath, import.meta.url), 'utf8'));

const [graph, handbook, matchesIndex, bridges, relays, readingNotesText] = await Promise.all([
  readJson('../public/data/graph_data.json'),
  readJson('../public/knowledge/data.json'),
  readJson('../public/syzygy/matches.json'),
  readJson('../src/syzygy/bridges.json'),
  readJson('../src/syzygy/matching-relays.json'),
  readFile(new URL('../../reference/reading_notes.yaml', import.meta.url), 'utf8'),
]);

const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
const entriesById = new Map(handbook.entries.map((entry) => [entry.id, entry]));

const NEW_L4_IDS = [
  'mech_pareidolia_apophenia',
  'mech_hypnagogic_hypnopompic',
  'mech_mass_psychogenic_illness',
  'mech_optical_mirage_refraction',
  'mech_auditory_evp_apophenia',
  'mech_grief_bereavement_hallucination',
  'theory_ostension_legend_tripping',
  'theory_liminality_rites_passage',
];

test('Phase 3 myth, creepypasta quarantine, and Layer 4 mechanism coverage', () => {
  const mythNodes = graph.nodes.filter((node) => node.genre === 'myth');
  assert.ok(mythNodes.length >= 46, `Expected >= 46 myth nodes, got ${mythNodes.length}`);

  const creepypastaNodes = graph.nodes.filter((node) => node.genre === 'creepypasta_ostension');
  assert.ok(creepypastaNodes.length >= 20, `Expected >= 20 creepypasta_ostension nodes, got ${creepypastaNodes.length}`);
  for (const node of creepypastaNodes) {
    assert.equal(node.is_fictional_quarantine, true, `${node.id} must have is_fictional_quarantine === true`);
  }

  const layer4Nodes = graph.nodes.filter((node) => node.z_layer === 4);
  assert.ok(layer4Nodes.length >= 20, `Expected >= 20 z_layer === 4 nodes, got ${layer4Nodes.length}`);

  for (const id of NEW_L4_IDS) {
    const node = nodesById.get(id);
    assert.ok(node, `Missing Layer 4 node ${id} in graph_data.json`);
    assert.equal(node.z_layer, 4, `${id} must have z_layer === 4`);
    assert.equal(node.reading?.kind, 'research', `${id} must have research reading note in graph_data.json`);
    assert.ok((node.reading?.paragraphs?.length ?? 0) >= 3, `${id} must have >= 3 reading paragraphs`);

    const yamlPattern = new RegExp(`^${id}:\\r?\\n  kind: research\\b`, 'm');
    assert.match(readingNotesText, yamlPattern, `${id} must have research reading note in reference/reading_notes.yaml`);

    const relayRules = relays.filter((rule) => rule.trigger === 'node_id' && rule.match === id);
    assert.ok(relayRules.length > 0, `${id} must appear in web/src/syzygy/matching-relays.json`);
    for (const rule of relayRules) {
      const entry = entriesById.get(rule.entry);
      assert.ok(entry?.body?.trim(), `${id} relay ${rule.id} points to missing/empty entry ${rule.entry}`);
    }

    const matchedRows = matchesIndex.matches[id] ?? [];
    assert.ok(matchedRows.length > 0, `${id} must have non-empty matched entries in matches.json`);
    for (const row of matchedRows) {
      assert.ok(entriesById.get(row.entry)?.body?.trim(), `${id} matched entry ${row.entry} must be non-empty`);
    }
  }
});

test('Phase 3 curated bridges SYZ-184 through SYZ-239 resolve to graph nodes and handbook entries', () => {
  assert.ok(bridges.length >= 239, `Expected >= 239 total bridges, got ${bridges.length}`);

  const bridgesById = new Map(bridges.map((bridge) => [bridge.id, bridge]));
  const phase3Bridges = [];
  for (let number = 184; number <= 239; number++) {
    const id = `SYZ-${number}`;
    const bridge = bridgesById.get(id);
    assert.ok(bridge, `Missing Phase 3 bridge ${id}`);
    phase3Bridges.push(bridge);
  }
  assert.equal(phase3Bridges.length, 56);

  for (const bridge of phase3Bridges) {
    const node = nodesById.get(bridge.case);
    const entry = entriesById.get(bridge.entry);
    assert.ok(node, `${bridge.id}: missing graph node ${bridge.case}`);
    assert.ok(entry?.body?.trim(), `${bridge.id}: missing or empty handbook entry ${bridge.entry}`);
    assert.equal(bridge.relation, 'THEMATIC', `${bridge.id}: expected relation === 'THEMATIC'`);
    assert.equal(bridge.related, null, `${bridge.id}: expected related === null`);
    assert.ok(bridge.rationale?.trim().length > 0, `${bridge.id}: missing rationale`);

    const curatedRows = (matchesIndex.matches[bridge.case] ?? []).filter(
      (row) => row.kind === 'curated' && row.bridge_id === bridge.id && row.entry === bridge.entry,
    );
    assert.equal(curatedRows.length, 1, `${bridge.id}: missing curated match row in matches.json`);
  }
});

test('catalogueBrowse REGIONS and nodeRegion route Phase 3 and existing regions accurately', () => {
  const regionIds = REGIONS.map((region) => region.id);
  assert.ok(regionIds.includes('south-asia'), 'REGIONS must include south-asia');
  assert.ok(regionIds.includes('middle-east'), 'REGIONS must include middle-east');
  assert.ok(regionIds.includes('southeast-asia'), 'REGIONS must include southeast-asia');
  assert.ok(regionIds.includes('oceania'), 'REGIONS must include oceania');

  const expectedRegions = [
    ['middle-east', [
      'case_iq_sumer_inanna_underworld',
      'case_iq_uruk_gilgamesh_flood',
      'case_iq_babylon_enuma_elish',
      'case_iq_eridu_adapa_wind',
      'case_sa_rubalkhali_jinn_lore',
      'case_ir_alborz_simurgh_lore',
      'case_tr_anatolia_nazar_amulet',
    ]],
    ['south-asia', [
      'case_in_purana_samudra_manthana',
      'case_in_vedic_manu_matsya_flood',
      'case_in_katha_nachiketa_yama',
      'case_in_chidambaram_shiva_nataraja',
      'case_in_ujjain_vetala_cycle',
      'case_np_khumbu_yeti_lore',
      'case_in_kerala_sarpakavu_naga',
    ]],
    ['europe', [
      'case_gr_eleusis_persephone_cycle',
      'case_it_rome_romulus_remus',
      'case_is_snorra_yggdrasil_ragnarok',
      'case_fi_karelia_kalevala_sampo',
      'case_ie_tara_tuatha_de_danann',
      'case_gb_dyfed_mabinogion_annwn',
      'case_ru_novgorod_perun_veles',
      'case_se_dalarna_tomte_lore',
      'case_ru_karelia_baba_yaga',
      'case_ua_dnipro_rusalka_lore',
      'case_it_friuli_benandanti_1575',
      'case_ru_uvb76_buzzer_station',
    ]],
    ['north-america', [
      'case_gt_quiche_popol_vuh_twins',
      'case_mx_teotihuacan_five_suns',
      'case_mx_mictlan_quetzalcoatl_bones',
      'case_ca_ontario_windigo_lore',
      'case_us_point_pleasant_mothman_1966',
      'case_scp_173_containment_2007',
      'case_local58_analog_horror_2015',
      'case_us_taos_hum_1993',
      'case_us_chicago_max_headroom_1987',
    ]],
    ['oceania', [
      'case_nz_aotearoa_maui_fishing',
      'case_nz_wellington_te_ika_a_maui',
      'case_us_kilauea_pele_lava_rock',
      'corpus_hawaiian_kumulipo',
    ]],
  ];

  for (const [expectedRegion, ids] of expectedRegions) {
    for (const id of ids) {
      const node = nodesById.get(id);
      assert.ok(node, `Missing node ${id} for region routing test`);
      assert.equal(nodeRegion(node), expectedRegion, `${id} should route to ${expectedRegion}`);
    }
  }

  const indonesiaNodes = graph.nodes.filter((node) => {
    const text = `${node.spatial?.culture_region ?? ''} ${node.spatial?.location_name ?? ''}`;
    return /indonesia|印尼|印度尼西亚/i.test(text);
  });
  assert.ok(indonesiaNodes.length > 0, 'Expected Indonesia nodes in graph_data.json');
  for (const node of indonesiaNodes) {
    assert.equal(nodeRegion(node), 'southeast-asia', `Indonesia node ${node.id} must stay in southeast-asia`);
  }

  for (let number = 184; number <= 239; number++) {
    const bridge = bridges.find((item) => item.id === `SYZ-${number}`);
    const region = nodeRegion(nodesById.get(bridge.case));
    assert.ok(region !== 'other' && region !== 'unspecified', `${bridge.id} (${bridge.case}) must not fall into ${region}`);
  }
});
