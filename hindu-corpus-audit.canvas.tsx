import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

const linkFailures = [
  ["403", "sacred-texts.com SBE and index pages (13 URLs)", "Switch to IA/Wikisource canonical links"],
  ["404", "archive.org/details/vivekachudamani00shan", "Use live item: archive.org/details/vivekachudamanio00sankrich"],
  ["404", "archive.org/details/Arthashastra_English_Translation", "Use live item: archive.org/details/kautilyas-arthashastra"],
  ["404", "archive.org/details/kaborautiliyaart00kautuoft", "Use live item: archive.org/details/kautilyas-arthashastra"],
  ["404", "archive.org/details/textsofwhiteyaju00grif", "Use live item: archive.org/details/textswhiteyajur00grifgoog or DLI variants"],
  ["503", "archive.org/download/textsofwhiteyaju00grif/..._djvu.txt", "Use alternative IA identifier + stream/download endpoint"],
  ["404", "archive.org/details/buddhacharitaorli00asvauoft", "Use live item: archive.org/details/buddhakaritaasv00cowegoog"],
  ["404", "gutenberg.org/cache/epub/10270/pg10270.txt", "Use canonical eBook URL and resolve actual txt link dynamically"],
  ["None", "xxx.supabase.co placeholder", "Treat as non-source placeholder; ignore for corpus legality"],
];

const corpusIssues = [
  ["BLOCK", "rigveda_griffith.txt", "Contains Project Gutenberg #12555 = Arthur Conan Doyle, not Rig Veda"],
  ["BLOCK", "sama_veda_griffith.txt", "Contains Project Gutenberg #16367 = Watch-Work-Wait, not Sama Veda"],
  ["BLOCK", "atharva_veda_griffith.txt", "Contains Project Gutenberg #16295 = Vedanta Sutras, not Atharva Veda"],
  ["FIX", "agni_purana_mn_dutt_vol2.txt", "Mostly Devanagari OCR noise; unusable for current English parser path"],
  ["BLOCK", "pg7452.txt", "Autobiography of a Yogi legal dispute; keep out of production index"],
  ["SEPARATE", "pg12956.txt", "Secondary academic source; keep in separate academic collection"],
  ["DELETE DUP", "brahma_sutras_ramanuja_sbe48_part1.txt", "Duplicate artifact of combined Ramanuja file"],
  ["DELETE DUP", "brahma_sutras_ramanuja_sbe48_part2.txt", "Duplicate artifact of combined Ramanuja file"],
  ["FIX", "ashtavakra_gita_richards.txt", "Has site chrome/header content before verses; parser should hard-trim preamble"],
  ["FIX", "thirukkural_pope.txt", "Large preface/catalog noise before real couplets; parser start-boundary needed"],
  ["REVIEW", "bhagavad_gita_telang_sbe08.txt", "Contains Gita + Sanatsujatiya + Anugita; split into 3 texts"],
];

const legalMatrix = [
  ["SAFE A", "Project Gutenberg public-domain texts", "Commercially usable when content is correctly matched to title"],
  ["SAFE A", "Internet Archive PD-era scans with item-level checks", "Use item identifiers + metadata snapshot"],
  ["SAFE A", "SuttaCentral Sujato corpus", "CC0 confirmed in local LICENSE.md"],
  ["SAFE A", "John Richards Ashtavakra translation", "Public-domain declaration present in corpus file"],
  ["SAFE C", "GRETIL", "Allowed only under your free-forever policy (NC-SA)"],
  ["SAFE C", "accesstoinsight", "Allowed only if product remains non-commercial"],
  ["BLOCK X", "Osho / Sadhguru / Krishnamurti / Prabhupada etc.", "Known active copyright enforcement"],
  ["VERIFY", "Ramana post-1931, Sivananda, some Tamil repositories", "Needs source-by-source legal proof before approval"],
];

const missingHighValue = [
  ["White Yajurveda (Griffith)", "archive.org/details/textswhiteyajur00grifgoog", "Replaces dead identifier in current registry"],
  ["Buddhacharita (Cowell)", "archive.org/details/buddhakaritaasv00cowegoog", "Replaces dead identifier in current registry"],
  ["Rig Veda (Griffith)", "archive.org/details/hymnsrigveda00unkngoog", "Current local Rig Veda file is incorrect"],
  ["Atharva Veda (Griffith)", "archive.org/details/hymnsatharvaved00unkngoog", "Current local Atharva file is incorrect"],
  ["Sama Veda (Griffith)", "archive.org/details/in.ernet.dli.2015.47949", "Current local Sama file is incorrect"],
  ["Gita Govinda (Arnold)", "gutenberg.org/ebooks/7733", "High-value Bhakti text, PD and live"],
  ["Laghu Yoga Vasistha", "gutenberg.org/ebooks/10270", "High-value Advaita text, currently missing"],
];

export default function HinduCorpusAuditCanvas() {
  return (
    <Stack gap={16}>
      <H1>Hindu Philosophy Corpus Audit</H1>
      <Text tone="secondary">
        Scope: workspace source registry + local corpus files. Source check window: current run. Corpus quality check: all local
        text artifacts in <Text as="span" weight="semibold">corpus/raw</Text> (excluding nested SuttaCentral non-txt metadata).
      </Text>

      <Grid columns={4} gap={12}>
        <Stat value="97" label="Unique source links checked" />
        <Stat value="76" label="Live links (HTTP 2xx/3xx)" tone="success" />
        <Stat value="21" label="Broken links (HTTP error/none)" tone="warning" />
        <Stat value="58" label="Local corpus text files profiled" />
      </Grid>

      <Callout tone="danger" title="Production Blockers">
        Do not ship current corpus as-is. Three files labeled as Vedas are wrong books, one legally risky text is still present,
        and one Purana file is OCR-corrupted for English ingestion.
      </Callout>

      <H2>Critical Corpus Findings</H2>
      <Table
        headers={["Decision", "File", "Why"]}
        rows={corpusIssues}
        columnAlign={["left", "left", "left"]}
        rowTone={["danger", "danger", "danger", "warning", "danger", "info", "warning", "warning", "warning", "warning", "warning"]}
        striped
      />

      <H2>Broken Link Inventory</H2>
      <Table headers={["Status", "Broken URL", "Immediate Fix"]} rows={linkFailures} columnAlign={["left", "left", "left"]} striped />
      <Text tone="tertiary" size="small">
        Source and time range: extracted from DATA-SOURCES.md, COMBINED-PLAN.md, and approved-sources.yaml in this workspace during
        this audit run.
      </Text>

      <Divider />

      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>Legal Safety Matrix</CardHeader>
          <CardBody>
            <Table headers={["Tier", "Source Type", "Usage Rule"]} rows={legalMatrix} columnAlign={["left", "left", "left"]} striped />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>Missing High-Value Corpus to Add</CardHeader>
          <CardBody>
            <Table headers={["Text", "Recommended Source", "Reason"]} rows={missingHighValue} columnAlign={["left", "left", "left"]} striped />
          </CardBody>
        </Card>
      </Grid>

      <Callout tone="info" title="Technical Hardening Checklist">
        1) Add pre-ingest file validation (title match + allowed source fingerprint), 2) reject ingestion on mismatch, 3) keep
        legal allowlist as executable gate, 4) isolate academic secondary corpora, 5) store license proof snapshots per source for
        future audits.
      </Callout>
    </Stack>
  );
}
