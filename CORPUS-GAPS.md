# Corpus Gaps — AntarDarshan

> Texts we want but don't have yet. Check off as added.
> Last updated: 2026-06-27

---

## Priority 1 — High value, clear public domain source

| Text | Translator | Source | Where to get |
|---|---|---|---|
| [ ] **Vishnu Purana** | H.H. Wilson (1840) | Tier A | sacred-texts.com/hin/vp/ — browse each book, save .txt files |
| [ ] **Gita Govinda** | Edwin Arnold (1875) | Tier A | sacred-texts.com/hin/gg/ — NOT on Gutenberg |
| [ ] **Buddhacharita** | E.B. Cowell (1894) | Tier A | sacred-texts.com/bud/sbe49/ OR archive.org/details/buddhacharitaorli00asvauoft |
| [ ] **White Yajur Veda** | R.T.H. Griffith (1899) | Tier A | sacred-texts.com/hin/wyv/ OR archive.org/details/textsofwhiteyaju00grif |
| [ ] **Sama Veda** | R.T.H. Griffith (1895) | Tier A | sacred-texts.com/hin/sv/ |
| [ ] **Agni Purana Vol. 2** | M.N. Dutt (1904) | Tier A | archive.org/details/in.ernet.dli.2015.406665 — djvu.txt |

**Once downloaded:** save to `corpus/raw/` with this naming convention:
```
vishnu_purana_wilson.txt
gita_govinda_arnold.txt
buddhacharita_cowell_1894.txt
white_yajur_veda_griffith.txt
sama_veda_griffith.txt
agni_purana_mn_dutt_vol2.txt
```
Then add each to `ingestion/process_all.py` + `backend/corpus_index.py` READABLE_SCRIPTURES (if clean text).

---

## Priority 2 — Important but needs copyright/source verification

| Text | Translator | Status | Notes |
|---|---|---|---|
| [ ] **Srimad Bhagavatam** (Books 1, 2, 11) | J.M. Sanyal (1929-34) | Verify per-volume copyright on archive.org | Most important Vaishnava scripture. Check `possible-copyright-status: NOT_IN_COPYRIGHT` on IA before downloading. |
| [ ] **Devi Bhagavata Purana** | Swami Vijnananda (1921-22) | Likely Tier A, verify IA | Shakta tradition. Published 1921-22, likely PD if US copyright not renewed. |
| [ ] **Avadhuta Gita** | Hari Prasad Shastri (1929) | Tier A, verify IA | 79 short verses on radical non-dual liberation. Try archive.org search "avadhuta gita shastri". |
| [ ] **Yoga Vasistha Laghu** | K. Narayanaswami Aiyer (1896) | Tier A | PG #10270 returns 404 — try archive.org search "laghu yoga vasistha". |
| [ ] **Narada Bhakti Sutras** | Verify pre-1928 translation | Tier A likely | Search archive.org for public domain English translation. |
| [ ] **Tattvartha Sutra** (Jain) | J.L. Jaini (1920) | Verify IA | Central Jain text. archive.org should have it. |

---

## Priority 3 — Future, needs work or licensing

| Text | Issue |
|---|---|
| **Shiva Purana** | No public domain English translation exists. All are Motilal Banarsidass (copyright). |
| **Bhagavata Purana complete** (all 12 books) | Need full per-volume copyright verification. |
| **Kashmir Shaivism** (Shiva Sutras, Pratyabhijnahridayam) | All English translations copyrighted (Jaideva Singh, Motilal). |
| **Tripura Rahasya** | Sri Ramanasramam copyright. |
| **Gospel of Sri Ramakrishna** | Nikhilananda translation (1942) copyrighted. |
| **Guru Granth Sahib** | Need structured English translation source. |
| **Jnaneshwari** | Best English translations copyrighted. |
| **Ramana Maharshi works** | Gray zone — Sri Ramanasramam actively enforces post-1931 works. |

---

## Already fixed but worth noting

| Issue | Resolution |
|---|---|
| Wrong Gutenberg IDs for Vishnu Purana (#9394), Sama Veda (#16367), Gita Govinda (#7733) | Those IDs point to unrelated books. Use sacred-texts.com directly for all three. |
| Agni Purana Vol 2 was never downloaded | File was missing from corpus/raw/. Needs fresh download from archive.org. |
