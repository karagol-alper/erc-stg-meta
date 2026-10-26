/* make_paper.js - build the research paper and the supplementary data document with docx-js */
const fs = require("fs");
const path = require("path");
const D = require("docx");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, AlignmentType,
        ImageRun, PageBreak, Footer, Header, PageNumber, BorderStyle, ShadingType, LevelFormat, PageOrientation,
        VerticalAlign, TableLayoutType, ExternalHyperlink } = D;

const ROOT = __dirname;
const FIG = path.join(ROOT, "outputs", "figures");
const TABLES = JSON.parse(fs.readFileSync(path.join(ROOT, "outputs", "paper_tables.json"), "utf8"));
const R = JSON.parse(fs.readFileSync(path.join(ROOT, "outputs", "results.json"), "utf8"));
const OUTDIR = "/mnt/user-data/outputs";

// ----------------------------------------------------------------------------- helpers
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function runs(text, base = {}) {
  // inline markup: **bold**, *italic*, ^superscript^
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|\^[^^]+\^)/g).filter(s => s.length);
  return parts.map(s => {
    if (s.startsWith("**")) return new TextRun({ ...base, text: s.slice(2, -2), bold: true });
    if (s.startsWith("^")) return new TextRun({ ...base, text: s.slice(1, -1), superScript: true });
    if (s.startsWith("*")) return new TextRun({ ...base, text: s.slice(1, -1), italics: true });
    return new TextRun({ ...base, text: s });
  });
}
function P(text, opts = {}) {
  return new Paragraph({ children: runs(text, opts.run || {}), alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 120, line: opts.line ?? 276 }, indent: opts.indent, keepNext: opts.keepNext });
}
function H(text, level) {
  const lv = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2, 3: HeadingLevel.HEADING_3 }[level];
  return new Paragraph({ text, heading: lv, keepNext: true });
}
function bullets(items, ref = "bullets") {
  return items.map(t => new Paragraph({ children: runs(t), numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 264 }, alignment: AlignmentType.JUSTIFIED }));
}
function numbered(items) { return bullets(items, "numbers"); }
function pageBreak() { return new Paragraph({ children: [new PageBreak()] }); }

function cell(text, opts = {}) {
  return new TableCell({
    width: { size: opts.width, type: WidthType.DXA },
    shading: opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill, color: "auto" } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 40, bottom: 40, left: 60, right: 60 },
    children: [new Paragraph({ children: runs(String(text), { size: opts.size, bold: opts.bold }), alignment: opts.align || AlignmentType.LEFT, spacing: { after: 0, line: 240 } })],
  });
}
function makeTable(t, opts = {}) {
  const total = opts.total || 9000;
  const ncol = t.columns.length;
  let widths = opts.widths || (t.widths ? (() => { const s = t.widths.reduce((a, b) => a + b, 0); const w = t.widths.map(x => Math.round(total * x / s)); w[w.length - 1] += total - w.reduce((a, b) => a + b, 0); return w; })() : null);
  if (!widths) {
    // proportional to max content length (bounded)
    const lens = t.columns.map((c, j) => Math.max(c.length, ...t.rows.map(r => (r[j] || "").length)));
    const capped = lens.map(l => Math.min(Math.max(l, 6), 60));
    const s = capped.reduce((a, b) => a + b, 0);
    widths = capped.map(l => Math.round(total * l / s));
    widths[ncol - 1] += total - widths.reduce((a, b) => a + b, 0);
  }
  const size = opts.size || (ncol > 12 ? 12 : ncol > 8 ? 14 : ncol > 5 ? 16 : 18);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
  const header = new TableRow({ tableHeader: true, children: t.columns.map((c, j) => cell(c, { width: widths[j], fill: "D9E2F3", bold: true, size })) });
  const body = t.rows.map((r, i) => new TableRow({ children: r.map((v, j) => cell(v, { width: widths[j], size, fill: i % 2 ? "F5F5F5" : undefined })) }));
  const table = new Table({ rows: [header, ...body], width: { size: total, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED,
    borders: { top: border, bottom: border, left: border, right: border, insideHorizontal: border, insideVertical: border } });
  const out = [new Paragraph({ children: runs(t.title, { bold: false, size: 20 }), spacing: { before: 200, after: 80 }, keepNext: true }), table];
  if (t.note) out.push(new Paragraph({ children: runs(t.note, { size: 16, italics: true }), spacing: { after: 200 } }));
  return out;
}
function figure(file, caption, widthPx = 600) {
  const sz = pngSize(file);
  const h = Math.round(widthPx * sz.h / sz.w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: widthPx, height: h } })] }),
    new Paragraph({ children: runs(caption, { size: 18 }), alignment: AlignmentType.JUSTIFIED, spacing: { after: 240 } }),
  ];
}
function refList(refs) {
  return refs.map((r, i) => new Paragraph({ children: runs(`${i + 1}. ${r}`, { size: 18 }), indent: { left: 360, hanging: 360 }, spacing: { after: 60, line: 250 }, alignment: AlignmentType.LEFT }));
}

const numbering = {
  config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ],
};
const styles = {
  default: { document: { run: { font: "Calibri", size: 21 } } },
  characterStyles: [{ id: "Hyperlink", name: "Hyperlink", run: { color: "0563C1", underline: {} } }],
  paragraphStyles: [
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, color: "1F3864", font: "Calibri" }, paragraph: { spacing: { before: 320, after: 120 }, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, color: "1F3864", font: "Calibri" }, paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1 } },
    { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 21, bold: true, italics: true, font: "Calibri" }, paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
  ],
};
function footer(text) {
  return new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: text + "  |  page ", size: 16, color: "666666" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "666666" })] })] });
}

// ----------------------------------------------------------------------------- author block
function link(text, url, size = 20) {
  return new ExternalHyperlink({ children: [new TextRun({ text, style: "Hyperlink", size })], link: url });
}
function authorBlock(size = 20) {
  const sup = (t) => new TextRun({ text: t, superScript: true, size: size + 2 });
  return [
    new Paragraph({ spacing: { after: 80 }, children: [
      new TextRun({ text: "Alper Karag\u00f6l", size: size + 2, bold: true }), sup("1,\u2020,*"),
      new TextRun({ text: ", Taner Karag\u00f6l", size: size + 2, bold: true }), sup("1,\u00b6,*") ] }),
    new Paragraph({ spacing: { after: 40 }, children: [sup("1"), new TextRun({ text: " Istanbul University Istanbul Medical Faculty, Istanbul, Turkey", size })] }),
    new Paragraph({ spacing: { after: 40 }, children: [sup("\u2020"), new TextRun({ text: " Present address: Broad Institute of MIT and Harvard, Cambridge, MA, USA; Department of Mechanical Engineering, Massachusetts Institute of Technology, Cambridge, MA, USA", size })] }),
    new Paragraph({ spacing: { after: 40 }, children: [sup("\u00b6"), new TextRun({ text: " Present address: McGovern Institute for Brain Research, Massachusetts Institute of Technology, Cambridge, MA, USA", size })] }),
    new Paragraph({ spacing: { after: 40 }, children: [sup("*"), new TextRun({ text: " To whom correspondence should be addressed: Alper Karag\u00f6l, ", size }), link("akaragol@mit.edu", "mailto:akaragol@mit.edu", size),
      new TextRun({ text: ", ORCID ", size }), link("0009-0001-7864-0732", "https://orcid.org/0009-0001-7864-0732", size),
      new TextRun({ text: "; Taner Karag\u00f6l, ", size }), link("karagolt@mit.edu", "mailto:karagolt@mit.edu", size),
      new TextRun({ text: ", ORCID ", size }), link("0009-0005-1011-7661", "https://orcid.org/0009-0005-1011-7661", size) ] }),
  ];
}

// ----------------------------------------------------------------------------- references
const refs = [
  "European Research Council. ERC Starting Grants – outcome: indicative statistics (per-call statistics documents, calls 2013 and 2015–2026). Brussels: ERC Executive Agency. Source URLs in Supplementary Table S1b.",
  "European Research Council. Starting Grants applications: facts and figures (per-call releases, 2018–2025 calls); secondary reporting of the 2026 release. Source URLs in Supplementary Table S1b.",
  "European Research Council. ERC gender statistics, December 2016; June 2022. https://erc.europa.eu/sites/default/files/document/file/Gender_statistics_Dec_2016.pdf",
  "EURAXESS. Gender equality policies and gender distribution in MSCA and ERC. 2018. https://euraxess.ec.europa.eu/worldwide/south-korea/gender-equality-policies-and-gender-distribution-msca-and-erc",
  "European Research Council. ERC funding activities 2007–2013. Brussels: ERC; 2014. https://erc.europa.eu/sites/default/files/publication/files/ERC_funding_activities_2007_2013.pdf",
  "ERC Scientific Council. Widening excellence: bridging the ERC gap for a truly pan-European Research Area. ERC Scientific Council white paper, 25 March 2026. https://erc.europa.eu/system/files/2026-03/Widening%20excellence%20-%20Bridging%20the%20ERC%20gap%20for%20a%20truly%20pan-European%20Research%20Area%20-%20ERC%20Scientific%20Council%20white%20paper.pdf (news release: https://erc.europa.eu/news-events/news/erc-calls-stronger-action-close-europes-research-performance-gap)",
  "European Research Council. ERC Starting Grants: €705 million to back Europe's next generation of researchers (2026 results). 3 September 2026. https://erc.europa.eu/news-events/news/erc-2026-starting-grants-results",
  "Ghirelli C, Havari E, Meroni EC, Verzillo S. The long-term causal effects of winning an ERC grant. IZA Discussion Paper No. 16108, 2023. https://docs.iza.org/dp16108.pdf",
  "Wang Y, Jones BF, Wang D. Early-career setback and future career impact. Nature Communications 2019;10:4331.",
  "Azoulay P, Graff Zivin JS, Manso G. Incentives and creativity: evidence from the academic life sciences. RAND Journal of Economics 2011;42:527–554.",
  "Schmaling KB, Gallo SA. Gender differences in peer reviewed grant applications, awards, and amounts: a systematic review and meta-analysis. Research Integrity and Peer Review 2023;8:2.",
  "Bornmann L, Mutz R, Daniel H-D. Gender differences in grant peer review: a meta-analysis. Journal of Informetrics 2007;1:226–238.",
  "Marsh HW, Bornmann L, Mutz R, Daniel H-D, O'Mara A. Gender effects in the peer reviews of grant proposals: a comprehensive meta-analysis comparing traditional and multilevel approaches. Review of Educational Research 2009;79:1290–1326.",
  "Burns KEA, Straus SE, Liu K, Rizvi L, Guyatt G. Gender differences in grant and personnel award funding rates at the Canadian Institutes of Health Research based on research content area: a retrospective analysis. PLoS Medicine 2019;16:e1002935.",
  "Mutz R, Bornmann L, Daniel H-D. Heterogeneity of inter-rater reliabilities of grant peer reviews and its determinants: a general estimating equations approach. PLoS ONE 2012;7:e48509.",
  "Cole S, Cole JR, Simon GA. Chance and consensus in peer review. Science 1981;214:881–886.",
  "Cicchetti DV. The reliability of peer review for manuscript and grant submissions: a cross-disciplinary investigation. Behavioral and Brain Sciences 1991;14:119–135.",
  "Hesselberg J-O, Ulleberg P, Sørensen Ø, Fostervold KI, Ingvaldsen SH, Svege I. Registered report protocol: factors associated with inter-rater agreement in grant peer review. PLoS ONE 2025;20(5):e0322696.",
  "Marsh HW, Jayasinghe UW, Bond NW. Improving the peer review process for grant applications: reliability, validity, bias, and generalizability. American Psychologist 2008;63:160–168.",
  "Bornmann L, Mutz R, Daniel H-D. A reliability-generalization study of journal peer reviews: a multilevel meta-analysis of inter-rater reliability and its determinants. PLoS ONE 2010;5:e14331.",
  "Jacob BA, Lefgren L. The impact of research grant funding on scientific productivity. Journal of Public Economics 2011;95:1168–1177.",
  "Bol T, de Vaan M, van de Rijt A. The Matthew effect in science funding. Proceedings of the National Academy of Sciences 2018;115:4887–4890.",
  "Herbert DL, Barnett AG, Clarke P, Graves N. On the time spent preparing grant proposals: an observational study of Australian researchers. BMJ Open 2013;3:e002800.",
  "Fang FC, Casadevall A. Research funding: the case for a modified lottery. mBio 2016;7:e00422-16.",
  "Stavropoulou C, Viney I. Impact of early career medical research funding on subsequent publication outcomes and research income for female and male applicants in the United Kingdom. Nature Communications 2026;17:7909. https://doi.org/10.1038/s41467-026-73009-z",
  "Bajgar M, Karapetyan S. Research grants and independent scientific contributions: evidence from authorship position. IES Working Papers 30/2025 (revised December 2025). Prague: Institute of Economic Studies, Charles University. https://ies.fsv.cuni.cz/en/research-grants-and-independent-scientific-contributions-evidence-authorship-position",
  "DerSimonian R, Laird N. Meta-analysis in clinical trials. Controlled Clinical Trials 1986;7:177–188.",
  "Paule RC, Mandel J. Consensus values and weighting factors. Journal of Research of the National Bureau of Standards 1982;87:377–385.",
  "Viechtbauer W. Confidence intervals for the amount of heterogeneity in meta-analysis. Statistics in Medicine 2007;26:37–52.",
  "Higgins JPT, Thompson SG. Quantifying heterogeneity in a meta-analysis. Statistics in Medicine 2002;21:1539–1558.",
  "IntHout J, Ioannidis JPA, Borm GF. The Hartung-Knapp-Sidik-Jonkman method for random effects meta-analysis is straightforward and considerably outperforms the standard DerSimonian-Laird method. BMC Medical Research Methodology 2014;14:25.",
  "Knapp G, Hartung J. Improved tests for a random effects meta-regression with a single covariate. Statistics in Medicine 2003;22:2693–2710.",
  "Higgins JPT, Thompson SG. Controlling the risk of spurious findings from meta-regression. Statistics in Medicine 2004;23:1663–1682.",
  "Robins J, Breslow N, Greenland S. Estimators of the Mantel-Haenszel variance consistent in both sparse data and large-strata limiting models. Biometrics 1986;42:311–323.",
  "Stijnen T, Hamza TH, Özdemir P. Random effects meta-analysis of event outcome in the framework of the generalized linear mixed model with applications in sparse data. Statistics in Medicine 2010;29:3046–3067.",
  "Egger M, Davey Smith G, Schneider M, Minder C. Bias in meta-analysis detected by a simple, graphical test. BMJ 1997;315:629–634.",
  "Peters JL, Sutton AJ, Jones DR, Abrams KR, Rushton L. Comparison of two methods to detect publication bias in meta-analysis. JAMA 2006;295:676–680.",
  "Begg CB, Mazumdar M. Operating characteristics of a rank correlation test for publication bias. Biometrics 1994;50:1088–1101.",
  "Duval S, Tweedie R. Trim and fill: a simple funnel-plot-based method of testing and adjusting for publication bias in meta-analysis. Biometrics 2000;56:455–463.",
  "Stanley TD, Doucouliagos H. Meta-regression approximations to reduce publication selection bias. Research Synthesis Methods 2014;5:60–78.",
  "Rücker G, Schwarzer G, Carpenter JR, Binder H, Schumacher M. Treatment-effect estimates adjusted for small-study effects via a limit meta-analysis. Biostatistics 2011;12:122–142.",
  "Baujat B, Mahé C, Pignon J-P, Hill C. A graphical method for exploring heterogeneity in meta-analyses: application to a meta-analysis of 65 trials. Statistics in Medicine 2002;21:2641–2652.",
  "Lash TL, Fox MP, Fink AK. Applying Quantitative Bias Analysis to Epidemiologic Data. New York: Springer; 2009.",
  "VanderWeele TJ, Ding P. Sensitivity analysis in observational research: introducing the E-value. Annals of Internal Medicine 2017;167:268–274.",
  "Ibrahim JG, Chen M-H. Power prior distributions for regression models. Statistical Science 2000;15:46–60.",
  "Wagenmakers E-J, Lodewyckx T, Kuriyal H, Grasman R. Bayesian hypothesis testing for psychologists: a tutorial on the Savage–Dickey method. Cognitive Psychology 2010;60:158–189.",
  "Spearman C. Correlation calculated from faulty data. British Journal of Psychology 1910;3:271–295; Brown W. Some experimental results in the correlation of mental abilities. British Journal of Psychology 1910;3:296–322.",
];
const K = {}; // citation keys -> numbers
["erc_stats", "erc_ff", "erc_gender", "euraxess", "erc_fp7", "erc_white", "erc_2026", "ghirelli", "wang", "azoulay", "schmaling", "bornmann07", "marsh09", "burns", "mutz12", "cole81", "cicchetti", "hesselberg", "marsh08", "bornmann10", "jacob", "bol", "herbert", "fang", "mrc26", "econlet26", "dl", "pm", "viecht", "ht02", "inthout", "kh", "ht04", "rbg", "stijnen", "egger", "peters", "begg", "duval", "stanley", "rucker", "baujat", "lash", "evalue", "ibrahim", "sd", "sb"].forEach((k, i) => K[k] = i + 1);
const c = (...keys) => "[" + keys.map(k => K[k]).join(",") + "]";

// ----------------------------------------------------------------------------- numbers used in text
const p = R.pooled_OR.REML_HKSJ, mh = R.pooled_OR.MH, rr = R.pooled_RR, rd = R.pooled_RD_pp;
const d = R.dynamics, g = R.geo, dm = R.domains, pol = R.policy, ev = R.evalues.RR_based, sel = R.selection_model, sens = R.sensitivity;
const bwk = R.bayes.HN["weakly informative (mu~N(0,1), tau~HN(0.5))"], bsc = R.bayes.HN["sceptical (mu~N(0,0.2), tau~HN(0.5))"];
const f = (x, n = 3) => Number(x).toFixed(n);
const pc = (x, n = 1) => (100 * x).toFixed(n);
const uk = g.association_contrasts[0], ch = g.association_contrasts[1];
const tx = d.tax_2026;
const pr = pol.propagated, rel = pol.reliability_meta;
const WID_APP_2024 = 940 / (940 + 7271);  // ERC white paper, March 2026: applications from widening vs non-widening countries, all schemes, 2024

// ----------------------------------------------------------------------------- main paper content
const T = TABLES.main;
const title = "Who gets an ERC Starting Grant, and does the selection machinery deserve the trust placed in it? A call-level meta-analysis of gender, geography, competition dynamics and selection policy with quantitative bias analysis";

const abstract = [
  P("**Background.** The European Research Council's Starting Grant (StG) is Europe's largest competitive scheme for early-career principal investigators. Two disparities recur in policy debate—the share of grants awarded to women and the concentration of grants in a few countries—yet published comparisons are single-call, unpooled and silent about the biases that separate equal success rates from equal treatment."),
  P("**Methods.** We treated each StG competition as a study. Ten consecutive calls (2017–2026; 34,536 evaluated proposals; 4,237 female or male grantees) contributed a 2×2 table of funding outcome by applicant gender, built from ERC per-call statistics and applicant-share releases (the latter rounded and encoded as intervals). We pooled log odds ratios with common-effect and random-effects estimators (Mantel–Haenszel, REML with Hartung–Knapp intervals, prediction intervals), tested trends by permutation, fitted exact-conditional hypergeometric-normal Bayesian models under alternative priors and historical power priors, and conducted quantitative bias analysis (probabilistic propagation of rounding and domain composition, E-values, and a latent-quality model of differential self-selection). Host-country grant counts for eleven calls (2013, 2015–2021, 2024–2026) supported analyses of widening-country shares, standardised grant ratios, concentration and framework-association shocks. We added a competition-dynamics module (success-rate meta-analysis, supply–demand decomposition, demand elasticity, application cost), a domain-neutrality module, and a decision-analytic simulator of selection mechanisms whose reliability input is a meta-analysis of published inter-rater reliabilities."),
  P(`**Results.** Women's success rate was ${pc(R.data.crude_sr_women, 2)}% versus ${pc(R.data.crude_sr_men, 2)}% for men; pooled OR ${f(p.est)} (95% CI ${f(p.lo)}–${f(p.hi)}), risk difference ${f(rd.est, 2)} percentage points (${f(rd.lo, 2)} to ${f(rd.hi, 2)}), with no between-call heterogeneity (I² = 0%, prediction interval ${f(p.pi_lo)}–${f(p.pi_hi)}) and no trend. Bayesian posterior probability of OR < 1 was ${f(bwk.P_OR_lt_1, 3)}, but Bayes factors were indecisive (BF₁₀ ${f(bwk.BF10, 2)}–${f(bsc.BF10, 2)}). Rounding and domain composition shifted the estimate by less than 0.01; a self-selection shift of only ${f(sel.breakeven_delta["1.0"], 2)}–${f(sel.breakeven_delta["0.5"], 2)} SD in the female applicant pool would account for the whole advantage, and a 0.2 SD shift is compatible with an evaluation-stage OR of 0.75–0.83. The FP7-era disadvantage (OR ≈ 0.78) has reversed. Widening Member States host ${pc(g.widening_eu.share, 1)}% (${pc(g.widening_eu.lo, 1)}–${pc(g.widening_eu.hi, 1)}%) of grants against ≈25% of the EU population; implied success-rate ratios are 0.25–0.40 under plausible applicant shares and ${f((g.widening_eu.share / WID_APP_2024) / ((1 - g.widening_eu.share) / (1 - WID_APP_2024)), 2)} at the 11% applicant share the ERC reports for 2024. The UK's share fell from ${pc(uk.baseline_share, 1)}% under Horizon 2020 to ${pc(uk.contrasts[1].share, 1)}% after re-association (OR ${f(uk.contrasts[1].odds_ratio, 2)}, ${f(uk.contrasts[1].lo, 2)}–${f(uk.contrasts[1].hi, 2)}). Success rates pool to ${pc(d.success_rate_pooled, 1)}% with a prediction interval of ${pc(d.success_rate_pi[0], 1)}–${pc(d.success_rate_pi[1], 1)}%; demand is inelastic to prior success rates, and the 2026 call cost applicants ${f(tx["20"].person_years_per_grant, 1)}–${f(tx["50"].person_years_per_grant, 1)} person-years per grant. Domain success rates are equalised by design while demand has shifted towards the social sciences and humanities. With a meta-analytic panel reliability of ${f(pr.rho_panel.median, 2)}, the ERC's two-stage evaluation adds ${f(pr.two_stage_gain_merit_SD.median, 2)} SD of funded merit; a threshold lottery would cost ${f(pr.threshold_lottery_cost_merit_SD.median, 2)} SD but narrow subgroup gaps.`),
  P("**Conclusions.** Since 2017 the StG shows no disadvantage for women at the level of success rates, but call-level parity is weak evidence about evaluation neutrality because the decisive quantity—the quality differential of applicant pools—is unobserved. The geographic gradient is an order of magnitude larger than the gender contrast, cohort luck and application cost are first-order inefficiencies, and the reliability of evaluation is the parameter that governs every reform trade-off. We list fourteen meta-analytic policy questions and the data the ERC would need to release to answer them."),
  P("**Keywords:** research funding; European Research Council; meta-analysis; gender; widening countries; peer review reliability; quantitative bias analysis; science policy.", { align: AlignmentType.LEFT }),
];

const intro = [
  H("1. Introduction", 1),
  P(`The European Research Council (ERC) Starting Grant funds early-career principal investigators with up to €1.5 million over five years. Between 2,700 and 4,800 proposals are evaluated in each annual call and 9–16% are funded ${c("erc_stats", "erc_2026")}. Because the scheme is large, prestigious and evaluated by a single two-step procedure, it has become the reference case in European debates about who gets funded. Two questions dominate: whether women are funded at the same rate as men, and whether researchers hosted in the "widening" Member States—countries with lower research intensity that hold about a quarter of the EU population—receive a fair share of grants ${c("erc_white")}.`),
  P(`The ERC publishes, for every call, the number of proposals by domain, the number of grantees by gender and host country, and, in a separate release, the rounded share of proposals submitted by women ${c("erc_stats", "erc_ff")}. These figures are routinely quoted one call at a time. Three things are missing from that practice. First, the calls are never pooled, so the precision of any statement about "the" gender gap is unknown and year-to-year noise is read as trend. Second, the biases that could distort a success-rate comparison are listed but not quantified: rounding of the published denominators, the different disciplinary composition of male and female applicant pools, and—decisively—differential self-selection into applying. Third, the comparison is never connected to the other properties of the competition that matter for policy: how volatile the success rate is, how applicants respond to it, how much effort the competition consumes, whether the budget rules that equalise success rates across domains are working, what association shocks do to the geography of grants, and how reliable the evaluation is that produces all of these outcomes.`),
  P(`This paper treats each StG competition as a study and applies the full apparatus of meta-analysis and quantitative bias analysis ${c("lash", "evalue")} to the ERC's own published data, then connects the results to a decision-analytic model of selection mechanisms in which the reliability of peer review is itself estimated by meta-analysis of the published literature ${c("mutz12", "cole81", "bornmann10")}. Our contribution is therefore methodological as much as substantive: we show what can and cannot be learned from call-level statistics, identify the specific data whose publication would resolve the remaining ambiguities, and quantify the trade-offs between the main reform options (two-stage evaluation, partial lotteries, budget dispersal) with uncertainty carried through from the evidence base.`),
  P("The paper is organised as follows. Section 2 describes the data and their provenance; Section 3 the statistical methods; Section 4 the results, in the order gender, sensitivity and history, geography and association status, competition dynamics, domains, and selection policy; Section 5 discusses interpretation, comparison with the quasi-experimental literature, policy implications and limitations. A supplementary document contains every table and figure produced by the analysis pipeline, and the code that reproduces them from the raw inputs."),
];

const data = [
  H("2. Data", 1),
  H("2.1 Primary gender series (10 calls, 2017–2026)", 2),
  P(`For each call the ERC's outcome statistics document gives the number of evaluated and selected proposals by domain (Life Sciences, LS; Physical Sciences and Engineering, PE; Social Sciences and Humanities, SH) and the number of grantees by gender ${c("erc_stats")}. The share of proposals submitted by women is published in the "facts and figures" release that follows each deadline ${c("erc_ff")}. It is reported to the nearest percentage point and usually qualified—"nearly 40%", "around 37%". We encoded every such statement as an interval ([X−1, X] for "nearly X%", [X−0.5, X+0.5] for "X%" or "around X%"), used the midpoint as the point estimate, and propagated the interval through the bias analysis (Section 3.5). The 2026 women's share ("nearly 43%") was obtained from secondary reporting of the ERC release and is flagged. Grantees who declared a non-binary gender (0–6 per call, 14 in total) were recorded separately and excluded from the female/male tables. Table 1 lists the resulting 2×2 tables; Supplementary Table S1 records every source and wording.`),
  ...makeTable(T.t1),
  H("2.2 Sensitivity series and historical comparators", 2),
  P(`Calls 2013, 2015 and 2016 have exact grantee counts by gender (or, for 2013, the rounded "30% women") but no located ERC release of the women's applicant share. For 2015–2016 we used a prior interval of 31–36%, bounded by the 30% reported for 2013, the 37% of 2017 that the ERC described as a record, and the 31% aggregate share of women among StG applicants for 2007–2016 in the ERC's gender statistics ${c("erc_gender")}; for 2013 we used 29–31% from a press report of ERC figures. These three calls enter sensitivity analyses only. The historical comparator for the FP7 era is the ERC's rounded StG success rates for 2007–2013 of 8% for women and 10% for men, as summarised by EURAXESS ${c("euraxess")}.`),
  H("2.3 Competition series, domains and geography", 2),
  P(`Evaluated and selected proposals were assembled for every call since 2007. Applications for 2007–2013 were verified against the ERC's *funding activities 2007–2013* report ${c("erc_fp7")}; the 2013 and 2015–2026 values against the outcome statistics documents ${c("erc_stats")}. Grant counts for 2007–2012 and both numbers for 2014 are as recalled from ERC results releases and are flagged in Supplementary Table S12; the verified series (k = 13) drives the main estimates. Domain splits are available for thirteen calls (2013, 2015–2026), and the 2025 document additionally gives grantees by domain × gender. Grantee counts by country of host institution were extracted from the bar-chart labels of the statistics documents for eleven calls (2013, 2015–2021, 2024–2026); the 2022 and 2023 charts carry no labels. Widening countries follow the Horizon Europe list (BG, HR, CY, CZ, EE, EL, HU, LV, LT, MT, PL, PT, RO, SK, SI); associated widening countries (e.g. TR, RS, UA) form a sensitivity set. Every count was checked against the published totals.`),
];

const methods = [
  H("3. Methods", 1),
  P("All methods were implemented from primary formulas in Python (numpy 2.4, scipy 1.17; no meta-analysis package), so that every step can be audited; the code is supplied with the supplementary material and regenerates every number, table and figure in about two minutes."),
  H("3.1 Effect sizes and pooling", 2),
  P(`The primary effect size is the log odds ratio (OR) of funding for women versus men, with the log risk ratio and the risk difference as secondary measures; all cells exceed 150, so no continuity correction was needed. We report the Mantel–Haenszel OR with the Robins–Breslow–Greenland variance ${c("rbg")}, the Peto OR, the inverse-variance common-effect estimate, and random-effects estimates with DerSimonian–Laird ${c("dl")}, Paule–Mandel ${c("pm")} and REML estimators of τ². Heterogeneity is described by Cochran's Q, I² with Higgins–Thompson intervals ${c("ht02")} and Q-profile intervals for τ² ${c("viecht")}. The primary interval is the Hartung–Knapp–Sidik–Jonkman t-based interval on the REML estimate ${c("inthout")}, and we give t-based 95% prediction intervals for the effect in a future call.`),
  H("3.2 Moderators, influence and small-study effects", 2),
  P(`Mixed-effects meta-regressions on call year (centred) and on programme era (Horizon Europe, calls ≥ 2021, versus Horizon 2020) used REML with Knapp–Hartung inference ${c("kh")} and permutation tests with 5,000 permutations, which retain nominal size for ten studies ${c("ht04")}. Influence was assessed by cumulative meta-analysis, leave-one-out re-estimation with a Cook's-distance analogue and externally studentised residuals, and Baujat decomposition ${c("baujat")}. Small-study effects were examined with Egger's ${c("egger")}, Peters' ${c("peters")} and Begg's ${c("begg")} tests, Duval–Tweedie L₀ trim-and-fill ${c("duval")}, PET-PEESE ${c("stanley")} and limit meta-analysis ${c("rucker")}; the last two extrapolate to zero standard error and are not identified when, as here, the standard errors vary only between 0.098 and 0.110, so they are reported but not interpreted.`),
  H("3.3 Bayesian analysis", 2),
  P(`Two hierarchical models were fitted by deterministic numerical integration on a (μ, τ) grid, which avoids Markov-chain diagnostics and is exactly reproducible: a normal–normal model on the log OR, and an exact-conditional hypergeometric–normal model in which the number of funded women in each call follows Fisher's non-central hypergeometric distribution given the table margins ${c("stijnen")}. Priors were μ ~ N(0, 1) (weakly informative) or N(0, 0.2) (sceptical) and τ ~ half-normal(0.5) or half-normal(0.1). We report posterior medians and 95% credible intervals, P(OR < 1), the posterior mass in a region of practical equivalence (0.91–1.10), Savage–Dickey Bayes factors ${c("sd")}, the posterior predictive distribution for a new call, and a power-prior analysis ${c("ibrahim")} in which the FP7-era aggregate is discounted by a₀ ∈ {0.05, 0.1, 0.25, 0.5, 1}.`),
  H("3.4 Quantitative bias analysis", 2),
  P(`Following the multiple-bias framework of Lash, Fox and Fink ${c("lash")}: (i) probabilistic bias analysis of the rounding of published applicant shares—each call's share was drawn uniformly from its interval, the 2×2 table rebuilt and the meta-analysis re-run (5,000 draws), with and without random error; (ii) external adjustment for domain composition—each call's observed domain-specific success rates were combined with an uncertain within-domain women's share (relative factors LS 1.15, PE 0.75, SH 1.30, each ±0.15, calibrated to the call's overall share) to obtain the OR that composition alone would induce, and the crude OR was corrected by it; (iii) E-values for the pooled risk ratio, its confidence limit, and non-null E-values for masking a true RR of 0.95 or 0.90 ${c("evalue")}; (iv) a latent-quality self-selection model in which women's applicant pool has merit N(δ, 1) and men's N(0, 1), the evaluation observes merit plus noise with reliability ρ, and a common threshold funds the observed share; the OR a fair evaluation would produce, OR_fair(δ, ρ), is compared with the observed OR to give the implied evaluation-stage OR and the break-even δ.`),
  H("3.5 Geography and association status", 2),
  P("The share of grants hosted in widening countries was pooled across calls on the logit scale (REML, Hartung–Knapp) with Clopper–Pearson intervals per call and a permutation trend test. Because applicant counts by country are not published, standardised grant ratios (observed/expected grants, the analogue of a standardised mortality ratio, with Garwood intervals) were computed under explicit scenarios for the widening countries' share of applicants (10%, 12.5%, 15%, 25%), and the implied success-rate ratio relative to the rest of Europe was derived. Concentration was summarised by the Gini coefficient, the Herfindahl index and top-3/top-5 shares; rank stability by Spearman correlations between consecutive calls. Framework-association shocks were analysed by logit-scale meta-regression of a country's share on period indicators (Horizon 2020 association; non-association; re-association) with Knapp–Hartung intervals and permutation tests, using a continuity correction only where a count is zero."),
  H("3.6 Competition dynamics", 2),
  P(`The call success rate was pooled on the logit scale (REML, Hartung–Knapp, prediction interval), and "cohort odds ratios"—the odds of funding for a proposal of given quality in one call relative to another—were computed for every pair of calls. Each consecutive change was decomposed as Δlog SR = Δlog G − Δlog N (grants versus applications). Demand elasticity was estimated by regressing Δlog N in call t on Δlog SR in call t−1 (the previous outcome is public when the next call's proposals are written), with heteroskedasticity-robust standard errors and a permutation test. Application cost was computed under 20, 34 and 50 working days per proposal (bracketing the 30–40 days reported for Australian NHMRC applicants ${c("herbert")}) and 220 working days per year, and expressed per grant and relative to the PI-years funded (grants × 5). The women's share of proposals was modelled by weighted linear regression on year, treating the rounding interval as uniform measurement error, with a bootstrap of the year at which a 50% share would be reached.`),
  H("3.7 Domains", 2),
  P("Equality of success rates across LS, PE and SH was tested within each call by chi-square and, across calls, by REML/Hartung–Knapp pooling of the log rate ratios SH:PE and LS:PE with permutation trend tests. Domain shares of proposals were regressed on year. For the 2025 call, the domain-specific gender ORs implied by three scenarios for the unpublished within-domain applicant shares were tabulated, together with the shares under which every domain OR would equal one."),
  H("3.8 Selection-mechanism simulation and evidence-to-decision", 2),
  P(`We simulated a competition of 3,500 applicants at the observed success rate (${pc(pol.inputs.success_rate, 1)}%) with a subgroup of ${pc(pol.inputs.share_w, 0)}% whose latent merit is shifted by −0.2 SD (a stylised widening-country pool). Latent merit is N(0, 1); a review stage observes merit plus noise with reliability ρ (the squared correlation between score and merit); two independent stages averaged have reliability 2ρ/(1+ρ) ${c("sb")}. Five mechanisms were compared: a single-stage panel funding the top K; an ERC-like two-stage design (stage 1 passes 30%, stage 2 adds an independent score, the mean of both ranks the finalists); a threshold-plus-lottery with a fundable pool of 2K ${c("fang")}; a merit-top-half-plus-lottery; and a pure lottery. Outcomes were the mean latent merit of the funded set, the share of the truly top-K applicants funded, the share of the true top 1% funded, the subgroup odds ratio, and the number of full reviews; 200 replications per value of ρ from 0.2 to 1.0.`),
  P(`To connect the simulator to evidence, published single-rater intraclass correlations of grant-review scores were pooled by REML/Hartung–Knapp: the Austrian Science Fund (0.259, 95% CI 0.249–0.279, 23,414 ratings) ${c("mutz12")}, the US National Science Foundation re-review study ${c("cole81")} (single-rater ICC 0.17–0.37 across fields as summarised by Cicchetti ${c("cicchetti")}, treated here as a 95% range), and a Norwegian funder (0.29, as reported by Hesselberg et al. ${c("hesselberg")}; standard error assumed 0.03). Panel reliability for 3 and 5 raters follows from the Spearman–Brown formula ${c("sb")}; propagation through the simulator drew the single-rater ICC from its pooled distribution plus an assumed between-funder SD of 0.05 and interpolated the simulator outputs over the ρ grid.`),
];

const results = [
  H("4. Results", 1),
  H("4.1 Pooled gender contrast", 2),
  P(`Across the ten calls, ${R.data.grants_women.toLocaleString("en-US")} of ${R.data.n_women.toLocaleString("en-US")} proposals by women and ${R.data.grants_men.toLocaleString("en-US")} of ${R.data.n_men.toLocaleString("en-US")} by men were funded (${pc(R.data.crude_sr_women, 2)}% versus ${pc(R.data.crude_sr_men, 2)}%). The estimators agree to the third decimal (Table 2): Mantel–Haenszel OR ${f(mh.est)} (${f(mh.lo)}–${f(mh.hi)}, p = ${f(mh.p, 3)}), REML with Hartung–Knapp ${f(p.est)} (${f(p.lo)}–${f(p.hi)}, p = ${f(p.p, 3)}); RR ${f(rr.est)} (${f(rr.lo)}–${f(rr.hi)}) and RD ${f(rd.est, 2)} pp (${f(rd.lo, 2)} to ${f(rd.hi, 2)}). Heterogeneity is absent (Q = ${f(p.Q, 2)}, p = ${f(p.p_Q, 2)}; I² = 0%, 95% CI 0–${pc(p.I2_hi, 0)}%; τ² = ${f(p.tau2, 4)}, Q-profile CI 0–${f(p.tau2_hi, 3)}), yet the prediction interval (${f(p.pi_lo)}–${f(p.pi_hi)}) shows that a future call with OR below one is entirely plausible (Figure 1). Per-call risk differences ranged from −0.6 to +2.7 percentage points (Figure 2).`),
  ...figure(path.join(FIG, "fig01_forest.png"), "**Figure 1.** Forest plot of the odds ratio for funding, women versus men, in ten ERC Starting Grant calls (2017–2026). Squares are proportional to random-effects weights; the diamonds give the REML/Hartung–Knapp random-effects estimate and the Mantel–Haenszel common-effect estimate; the dotted bar is the 95% prediction interval."),
  ...makeTable(T.t2),
  ...figure(path.join(FIG, "fig02_success_rates.png"), "**Figure 2.** Success rates by gender with Wilson 95% intervals (left) and per-call risk differences (right)."),
  H("4.2 Trend, influence and small-study diagnostics", 2),
  P(`Meta-regression on call year gave a slope of ${R.metareg_year.beta[1].toFixed(4)} log-OR per year (95% CI ${R.metareg_year.ci_lo[1].toFixed(3)} to ${R.metareg_year.ci_hi[1].toFixed(3)}; Knapp–Hartung p = ${f(R.metareg_year.p[1], 2)}; permutation p = ${f(R.metareg_year.perm_p, 2)}), an OR ratio of ${f(R.metareg_year.or_change_per_decade, 2)} per decade; the Horizon Europe era differed from Horizon 2020 by a factor ${f(R.metareg_era.or_ratio, 3)} (${f(R.metareg_era.ci[0], 3)}–${f(R.metareg_era.ci[1], 3)}; permutation p = ${f(R.metareg_era.perm_p, 2)}). The cumulative estimate has been stable since 2020; omitting any one call moves the pooled OR only between ${f(R.influence.loo_OR_range[0])} and ${f(R.influence.loo_OR_range[1])} (largest Cook's D ${f(R.influence.max_cook, 2)}, for ${R.influence.max_cook_call}; largest |studentised residual| ${f(R.influence.max_abs_rstudent, 2)}). Egger's intercept was ${f(R.small_study.egger.intercept, 2)} (p = ${f(R.small_study.egger.p, 2)}), Peters' test p = ${f(R.small_study.peters.p, 2)}, Begg's p = ${f(R.small_study.begg.p, 2)}; trim-and-fill imputed one call on the right and gave ${f(R.small_study.trim_fill.OR)} (${f(R.small_study.trim_fill.lo)}–${f(R.small_study.trim_fill.hi)}). Because all calls are of similar size, funnel-based methods have almost no leverage in this design (Supplementary Figures S1–S3).`),
  H("4.3 Bayesian analysis", 2),
  P(`Under the exact-conditional model with weakly informative priors, the posterior median OR was ${f(bwk.OR_median)} (95% CrI ${f(bwk.OR_lo)}–${f(bwk.OR_hi)}), P(OR < 1) = ${f(bwk.P_OR_lt_1, 3)}, P(0.91 < OR < 1.10) = ${f(bwk.P_ROPE, 2)} and P(OR > 1.10) = ${f(bwk.P_OR_gt_1p10, 2)}; the posterior median of τ was ${f(bwk.tau_median, 3)} (97.5th percentile ${f(bwk.tau_hi, 2)}) and the predictive interval for the next call ${f(bwk.pred_OR_lo, 2)}–${f(bwk.pred_OR_hi, 2)} (Figure 3). The Savage–Dickey Bayes factor was ${f(bwk.BF10, 2)} under the N(0, 1) prior and ${f(bsc.BF10, 2)} under the sceptical prior: the data do not discriminate strongly between "no difference" and "a small female advantage". The marginal maximum-likelihood estimate of the same model was ${f(R.bayes.HN_MLE.OR)} (profile CI ${f(R.bayes.HN_MLE.lo)}–${f(R.bayes.HN_MLE.hi)}), and the normal–normal model agreed to two decimals. With the FP7-era aggregate (OR ${f(R.bayes.historical_comparator.OR, 2)}) discounted to a₀ = 0.1 the posterior was ${f(R.bayes.power_prior[2].OR_median)} (${f(R.bayes.power_prior[2].lo)}–${f(R.bayes.power_prior[2].hi)}), and only at a₀ ≥ 0.5 did the historical disadvantage pull the posterior below one (Table 4).`),
  ...figure(path.join(FIG, "fig06_bayesian.png"), "**Figure 3.** Bayesian analysis with the exact-conditional hypergeometric–normal model: posterior of the mean OR under three priors (dotted: priors), posterior of the between-call SD τ, posterior predictive distribution for a new call, and sensitivity to a power prior built from the FP7-era aggregate."),
  H("4.4 Quantitative bias analysis", 2),
  P(`Table 3 summarises the bias analyses and Figure 4 displays them. Rounding of the published applicant shares moved the pooled OR by less than 0.01 in systematic terms (${f(R.pba.denominator_only.systematic.median)}, 95% simulation interval ${f(R.pba.denominator_only.systematic.lo)}–${f(R.pba.denominator_only.systematic.hi)}) although it can shift individual calls by up to 4% (2026). Because the ERC allocates panel budgets in proportion to demand, success rates barely differ across domains, and the confounding OR that domain composition alone would induce ranged from ${f(Math.min(...Object.values(R.pba.domain_confounding_OR_point)))} to ${f(Math.max(...Object.values(R.pba.domain_confounding_OR_point)))}; the combined bias-adjusted estimate with random error was ${f(R.pba.denominator_plus_domain.total.median)} (${f(R.pba.denominator_plus_domain.total.lo)}–${f(R.pba.denominator_plus_domain.total.hi)}). The E-value for the pooled RR was ${f(ev.evalue_point, 2)} (${f(ev.evalue_ci, 2)} for the confidence limit); an unmeasured factor would need associations of ${f(ev["evalue_true_0.9"], 2)} with both gender and funding to mask a true RR of 0.90.`),
  P(`The self-selection model is decisive for interpretation. With the observed pool (${pc(sel.share_w, 1)}% women, ${pc(sel.success_rate, 2)}% success), a fair evaluation with perfect reliability would produce OR = ${f(p.est)} if the female applicant pool were shifted by only δ = ${f(sel.breakeven_delta["1.0"], 3)} SD (${f(sel.breakeven_delta["0.7"], 3)} at ρ = 0.7; ${f(sel.breakeven_delta["0.5"], 3)} at ρ = 0.5). If women self-select more stringently by 0.2 SD, the observed OR implies an evaluation-stage OR of ${f(T.t3.rows[11][1].split(" / ")[0])} at ρ = 1 and ${f(T.t3.rows[11][1].split(" / ")[2])} at ρ = 0.5 (Figure 4b). The success-rate contrast is thus consistent with neutrality, with a small female advantage, and with a moderate female disadvantage at the evaluation stage, depending on a quantity that call-level data cannot identify.`),
  ...makeTable(T.t3),
  ...figure(path.join(FIG, "fig07_bias_analysis.png"), "**Figure 4a.** Probabilistic bias analysis (median and 95% simulation interval of the pooled OR), the confounding factor induced by domain composition in each call, and the E-value curve for the pooled RR.", 600),
  ...figure(path.join(FIG, "fig08_selection_sensitivity.png"), "**Figure 4b.** Differential self-selection: the OR a fair evaluation would produce as a function of the quality shift δ of the female applicant pool for three reliabilities (left), and the evaluation-stage OR implied by the observed pooled OR (right).", 600),
  H("4.5 Sensitivity analyses and historical reversal", 2),
  P(`Removing non-binary grantees from the denominator or using the 2023 reserve-list counts changed nothing (Table 4). Adding the 2013, 2015 and 2016 calls with imputed applicant shares lowered the pooled OR to ${f(sens.extended_2015_2026_imputed_MC.OR_median)} (${f(sens.extended_2015_2026_imputed_MC.lo_total)}–${f(sens.extended_2015_2026_imputed_MC.hi_total)}) and introduced heterogeneity (median I² ${pc(sens.extended_2015_2026_imputed_MC.I2_median, 0)}%), with a positive trend of about ${pc(sens.extended_trend.or_ratio_per_decade - 1, 0)}% per decade that is not significant with thirteen calls (permutation p = ${f(sens.extended_trend.perm_p, 2)}; Supplementary Figure S4). The FP7-era comparator (OR ${f(sens.fp7_comparator_OR_range.point, 2)}, rounding range ${f(sens.fp7_comparator_OR_range.lo, 2)}–${f(sens.fp7_comparator_OR_range.hi, 2)}) and the 2007–2016 share-based OR of ${f(sens.stg_2007_2016_share_based_OR.value, 2)} confirm that the pre-2017 disadvantage was real: the series has moved from OR ≈ 0.8 to ≈ 1.08, a change of roughly 0.3 on the log-odds scale that coincides with the rise in the women's share of applicants from 30% to 43%.`),
  ...makeTable(T.t4),
  P(`Expressed as grants, had women been funded at men's rate in each call, ${f(R.counterfactual.cumulative_excess_women_grants, 0)} fewer grants (95% CI ${f(R.counterfactual.lo, 0)}–${f(R.counterfactual.hi, 0)}) would have gone to women over 2017–2026, about twelve per call, with 2024 the only call in which the excess is individually distinguishable from zero (Supplementary Table S10).`),
  H("4.6 Geography and association status", 2),
  P(`Widening Member States host ${pc(g.widening_eu.share, 2)}% of StG grants (95% CI ${pc(g.widening_eu.lo, 2)}–${pc(g.widening_eu.hi, 2)}%; I² = 0%; year slope on the logit scale ${g.widening_eu.trend_beta > 0 ? "+" : ""}${f(g.widening_eu.trend_beta, 3)}, permutation p = ${f(g.widening_eu.trend_perm_p, 2)}), or ${pc(g.widening_any.share, 1)}% including associated widening countries, against roughly 25% of the EU population ${c("erc_white")} (Figure 5, Table 5). Standardised grant ratios were 0.42, 0.34, 0.28 and 0.17 for assumed applicant shares of 10%, 12.5%, 15% and 25%, corresponding to success-rate ratios of 0.40, 0.31, 0.25 and 0.13 against the rest of Europe. The ERC's white paper reports, for all ERC schemes in 2024, 940 applications from widening countries against 7,271 from the rest (an applicant share of ${pc(WID_APP_2024, 1)}%) ${c("erc_white")}; at that share the StG standardised grant ratio is ${f(g.widening_eu.share / WID_APP_2024, 2)} and the implied success-rate ratio ${f((g.widening_eu.share / WID_APP_2024) / ((1 - g.widening_eu.share) / (1 - WID_APP_2024)), 2)}, consistent with the white paper's reported success rates of 1–7% versus about 11%. Bringing widening hosts to parity at those shares would have required 24–44 additional grants per call (6–11% of all grants).`),
  ...figure(path.join(FIG, "fig09_geography.png"), "**Figure 5.** Share of StG grants hosted in widening Member States by call with exact intervals and the pooled estimate (left); standardised grant ratios under applicant-share scenarios (middle); concentration of grants across host countries (right)."),
  P(`Concentration is stable to slightly declining (mean Gini ${f(g.concentration.gini_mean, 2)}; top-5 share ${pc(g.concentration.top5_mean, 0)}% on average, 67% in 2013 and 58% in 2026; 22–25 countries host at least one grant), and the host-country ranking is highly persistent (Spearman ρ between consecutive calls ${f(g.rank_stability.consecutive_spearman_min, 2)}–0.96). Against this stability, framework-association shocks stand out (Figure 6). The United Kingdom hosted ${pc(uk.baseline_share, 1)}% of StGs under Horizon 2020; during its non-association (2021–2023, proposals funded through the UKRI guarantee) the share was ${pc(uk.contrasts[0].share, 1)}% (OR ${f(uk.contrasts[0].odds_ratio, 2)}, ${f(uk.contrasts[0].lo, 2)}–${f(uk.contrasts[0].hi, 2)}), and after re-association (2024–2026) ${pc(uk.contrasts[1].share, 1)}% (OR ${f(uk.contrasts[1].odds_ratio, 2)}, ${f(uk.contrasts[1].lo, 2)}–${f(uk.contrasts[1].hi, 2)}; permutation p = ${f(uk.perm_p_first_contrast, 3)})—the loss has so far been permanent. Germany's share rose from ${pc(g.DE_share_first_last[0], 0)}% to ${pc(g.DE_share_first_last[1], 0)}% over the same period. Switzerland's share was unaffected in 2021 (OR ${f(ch.contrasts[0].odds_ratio, 2)}), was mechanically zero in 2024 when Swiss institutions could not host, and returned to 7–9% from 2025 (OR ${f(ch.contrasts[2].odds_ratio, 2)}, ${f(ch.contrasts[2].lo, 2)}–${f(ch.contrasts[2].hi, 2)}). Israel's share fell from 11% in 2013 to 2–3% in 2025–2026, a change unrelated to association status that we record without interpretation.`),
  ...figure(path.join(FIG, "fig14_country_shares_association.png"), "**Figure 6.** Host-country shares of StG grants for six countries with exact intervals and the association periods shaded (left); odds ratios of hosting a grant relative to the Horizon 2020 period from logit meta-regression (middle); concentration indices over time (right)."),
  ...makeTable(T.t5),
  H("4.7 Competition dynamics", 2),
  P(`The success rate is anything but a constant of the scheme (Figure 7, Table 6). Pooled over the thirteen verified calls it is ${pc(d.success_rate_pooled, 1)}% (95% CI ${pc(d.success_rate_ci[0], 1)}–${pc(d.success_rate_ci[1], 1)}%), but the between-call SD on the logit scale is ${f(d.success_rate_tau_logit, 2)} (I² = ${pc(d.success_rate_I2, 0)}%) and the prediction interval is ${pc(d.success_rate_pi[0], 1)}–${pc(d.success_rate_pi[1], 1)}%. Pairwise cohort odds ratios range from ${f(d.cohort_or_range[0], 2)} to ${f(d.cohort_or_range[1], 2)}: a proposal of given quality had ${pc(1 - d.cohort_or_2026_vs_2024, 0)}% lower odds of funding in 2026 than in 2024. The 2025→2026 change decomposes into ${(100 * d.last_change.dlogN).toFixed(1)} log-points of applications and ${(100 * d.last_change.dlogG).toFixed(1)} log-points of grants (${(100 * d.last_change.dlogSR).toFixed(1)} log-points of success rate, ${pc(d.last_change.demand_share, 0)}% attributable to demand). Demand does not respond materially to the previous call's success rate: the elasticity is ${d.elasticity_verified.elasticity.toFixed(2)} (robust SE ${f(d.elasticity_verified.se, 2)}; permutation p = ${f(d.elasticity_verified.perm_p, 2)}) in the verified series and ${d.elasticity_full.elasticity.toFixed(2)} (SE ${f(d.elasticity_full.se, 2)}; p = ${f(d.elasticity_full.perm_p, 2)}) in the extended series; the one large negative response—the 2022 fall after the 2021 surge—followed a one-off widening of the eligibility window, not a price signal.`),
  P(`Because applications do not fall when success rates fall, the scheme's application cost grows with demand. For the 2026 call the 4,807 proposals represent ${f(tx["20"].applicant_person_years, 0)}, ${f(tx["34"].applicant_person_years, 0)} or ${f(tx["50"].applicant_person_years, 0)} person-years of preparation at 20, 34 or 50 working days per proposal—${f(tx["20"].person_years_per_grant, 1)}, ${f(tx["34"].person_years_per_grant, 1)} or ${f(tx["50"].person_years_per_grant, 1)} person-years per grant, equivalent to ${pc(tx["20"].tax_ratio, 0)}–${pc(tx["50"].tax_ratio, 0)}% of the PI-years the call funds. The women's share of proposals rose by ${f(d.women_share_slope_pp_per_year, 2)} pp per year (SE ${f(d.women_share_slope_se, 2)}; p < 0.001) and the grantee share by ${f(d.grantee_share_slope_pp_per_year, 2)} pp per year; the representation gap (grantee minus applicant share) was positive in seven of ten calls but individually significant only in 2024. A linear extrapolation reaches a 50% applicant share around ${f(d.parity_year_point, 0)} (bootstrap interval ${f(d.parity_year_ci[0], 0)}–${f(d.parity_year_ci[1], 0)}).`),
  ...figure(path.join(FIG, "fig12_competition_dynamics.png"), "**Figure 7.** Competition dynamics: success rate by call with the pooled estimate and prediction interval (bars: evaluated proposals; grey bars partly recalled); supply–demand decomposition of consecutive changes; demand response to the previous call's success rate; and the women's share of proposals and of grantees with the fitted trend and parity projection."),
  ...makeTable(T.t6),
  H("4.8 Domain neutrality and the shift of demand", 2),
  P(`The rule that panel budgets follow requested budgets makes the three domains' success rates nearly identical (Figure 8, Table 7): no call rejects equality (all χ² p > 0.05; largest within-call max/min ratio ${f(dm.max_max_min_ratio, 2)} in ${dm.year_max}, median ${f(dm.median_max_min_ratio, 2)}). Pooled over thirteen calls the SH:PE rate ratio is ${f(dm.rr["SH vs PE"].RR, 2)} (${f(dm.rr["SH vs PE"].lo, 2)}–${f(dm.rr["SH vs PE"].hi, 2)}) and LS:PE ${f(dm.rr["LS vs PE"].RR, 2)} (${f(dm.rr["LS vs PE"].lo, 2)}–${f(dm.rr["LS vs PE"].hi, 2)}), both with I² = 0%; the SH:PE ratio has risen by ${pc(dm.rr["SH vs PE"].trend_per_year, 1)}% per year (permutation p = ${f(dm.rr["SH vs PE"].trend_perm_p, 2)}), closing an early SH disadvantage. Demand has migrated: SH proposals grew from ${pc(dm.app_share_trends.SH.first, 1)}% to ${pc(dm.app_share_trends.SH.last, 1)}% of the total (${dm.app_share_trends.SH.slope_pp_per_year.toFixed(2)} pp per year), while LS fell from ${pc(dm.app_share_trends.LS.first, 1)}% to ${pc(dm.app_share_trends.LS.last, 1)}% and PE from ${pc(dm.app_share_trends.PE.first, 1)}% to ${pc(dm.app_share_trends.PE.last, 1)}% (all permutation p ≤ 0.002). Because budgets follow demand, this shift has moved money towards the social sciences and humanities without an explicit decision.`),
  P(`For 2025, the only call with a gender × domain split of grantees (women 55/64/82, men 79/133/59 in LS/PE/SH), the domain-specific ORs depend entirely on the unpublished within-domain applicant shares: under a uniform 40% share they would be 1.05 (LS), 0.69 (PE) and 2.31 (SH); under the central scenario (LS 45%, PE 29%, SH 51%) 0.84, 1.19 and 1.42 (Supplementary Table S13b). The applicant shares that would make every domain exactly neutral are LS ${pc(dm.gender_domain_neutral_shares_2025.LS, 0)}%, PE ${pc(dm.gender_domain_neutral_shares_2025.PE, 0)}% and SH ${pc(dm.gender_domain_neutral_shares_2025.SH, 0)}%, averaging ${pc(dm.gender_domain_neutral_overall_2025, 1)}% against the published 40%. The sign of any domain-specific gender effect is therefore unidentified from public data.`),
  ...figure(path.join(FIG, "fig13_domains.png"), "**Figure 8.** Domain structure: success rates by domain per call (left); per-call SH:PE and LS:PE rate ratios with the pooled estimates (middle); domain shares of evaluated proposals with linear trends (right)."),
  ...makeTable(T.t7),
  H("4.9 Selection mechanisms and the value of reliability", 2),
  P(`Figure 9 sweeps the reliability of a review stage from 0.2 to 1.0. At ρ = 0.5 the funded set's mean latent merit is ${f(pol["at_rho_0.5"]["single-stage panel"].mean_merit, 2)} SD under a single-stage panel, ${f(pol["at_rho_0.5"]["two-stage (ERC-like)"].mean_merit, 2)} under the ERC-like two-stage design (precision from ${pc(pol["at_rho_0.5"]["single-stage panel"].share_topK, 0)}% to ${pc(pol["at_rho_0.5"]["two-stage (ERC-like)"].share_topK, 0)}% of the true top-K funded, with 1,050 instead of 3,500 full reviews), ${f(pol["at_rho_0.5"]["threshold + lottery"].mean_merit, 2)} under a threshold-plus-lottery, ${f(pol["at_rho_0.5"]["merit top-half + lottery"].mean_merit, 2)} under a merit-top-half-plus-lottery and ${f(pol["at_rho_0.5"]["pure lottery"].mean_merit, 2)} under a pure lottery (Table 8). A subgroup whose pool is shifted by −0.2 SD has an OR of ${f(pol["at_rho_0.5"]["single-stage panel"].subgroup_OR, 2)} under the single-stage panel, ${f(pol["at_rho_0.5"]["two-stage (ERC-like)"].subgroup_OR, 2)} under two-stage and ${f(pol["at_rho_0.5"]["threshold + lottery"].subgroup_OR, 2)} under threshold-plus-lottery: merit ranking amplifies pool differences, and the amplification grows with reliability.`),
  ...figure(path.join(FIG, "fig11_policy_simulation.png"), "**Figure 9.** Selection-mechanism simulation: mean latent merit of the funded set, share of the truly top-K applicants funded, and odds ratio for a subgroup with a −0.2 SD pool shift, as functions of stage reliability (shaded: literature range); and the budget-dispersal curve for output ∝ size^α."),
  P(`Pooling the three documented single-rater intraclass correlations gives ${f(rel.pooled_single_rater)} (${f(rel.lo)}–${f(rel.hi)}); by Spearman–Brown a three-rater panel reaches ${f(rel.panel_3_raters, 2)}, a five-rater panel ${f(rel.panel_5_raters, 2)}, and two independent five-rater stages ${f(rel.two_stage_of_5_rater_panels, 2)}—the mechanism by which the ERC's two-step design approaches conventionally "acceptable" reliability (Figure 10). Propagating a five-rater reliability of ${f(pr.rho_panel.median, 2)} (${f(pr.rho_panel.lo, 2)}–${f(pr.rho_panel.hi, 2)}) through the simulator, the two-stage design adds ${f(pr.two_stage_gain_merit_SD.median, 2)} SD (${f(pr.two_stage_gain_merit_SD.lo, 2)}–${f(pr.two_stage_gain_merit_SD.hi, 2)}) of mean funded merit; a threshold-plus-lottery costs ${f(pr.threshold_lottery_cost_merit_SD.median, 2)} SD (${f(pr.threshold_lottery_cost_merit_SD.lo, 2)}–${f(pr.threshold_lottery_cost_merit_SD.hi, 2)}) and ${pc(pr.threshold_lottery_topK_loss.median, 0)} points (${pc(pr.threshold_lottery_topK_loss.lo, 0)}–${pc(pr.threshold_lottery_topK_loss.hi, 0)}) of precision while raising the disadvantaged subgroup's OR by ${f(pr.threshold_lottery_disparity_gain_OR.median, 2)}; a merit-top-half-plus-lottery costs ${f(pr.hybrid_lottery_cost_merit_SD.median, 2)} SD (${f(pr.hybrid_lottery_cost_merit_SD.lo, 2)}–${f(pr.hybrid_lottery_cost_merit_SD.hi, 2)}). The reliability uncertainty changes the size of these effects, not their ordering.`),
  ...figure(path.join(FIG, "fig15_reliability_to_policy.png"), "**Figure 10.** Evidence-to-decision: pooled single-rater reliability of grant-review scores (left), the Spearman–Brown curve for panels of increasing size (middle), and the distributions of the simulated policy effects when the panel reliability is drawn from the meta-analytic distribution (right)."),
  ...makeTable(T.t8, { size: 12 }),
];

const discussion = [
  H("5. Discussion", 1),
  H("5.1 Principal findings", 2),
  P(`On the gender question, the ERC Starting Grant record since 2017 shows no disadvantage for women at the level of success rates. The best estimate is a small advantage (OR 1.085), robust to every estimator, influence check and bias adjustment applied, but its evidential weight against exact parity is modest: the Bayes factor is between 0.3 and 1.4 depending on the prior, and the prediction interval spans one. This is consistent with recent syntheses across funders, which find award rates approximately equal (a 1% difference favouring men with a confidence interval from −1% to +3% in the meta-analysis of Schmaling and Gallo ${c("schmaling")}) while older syntheses found men favoured by about 7% in odds ${c("bornmann07", "marsh09")} and single funders still show deficits for women (RR 0.89 at the Canadian Institutes of Health Research ${c("burns")}). The ERC's own trajectory—from OR ≈ 0.78 in the FP7 era to ≈ 1.08 now—mirrors that narrowing.`),
  P(`The central methodological message is that parity of success rates is not evidence of neutral evaluation. Success is measured conditional on applying, and the quantity that separates fair from biased evaluation—the difference in latent quality between the male and female applicant pools—is unobserved in call-level data. The break-even differential is only 0.04–0.06 SD; a differential of 0.2 SD, well within the range implied by the literature on women applying only when highly qualified, would turn the observed advantage into an evaluation-stage disadvantage of 17–25%. The same logic applies to reverse claims: a call with OR = 0.9 would not, by itself, demonstrate bias. Resolving this requires applicant-level pre-application productivity, which only the ERC holds. Quasi-experimental studies of other funders that do have such data find that the benefit of funding differs by gender—funded women gained more citations and field-normalised influence than unfunded women at the UK Medical Research Council, with no such effect for men ${c("mrc26")}—and that the marginal grant mainly buys PI-led output (first/last-author publications up by about 40% against 17% for all publications in a regression-discontinuity study of Czech medical grants ${c("econlet26")}); both argue for the same applicant-level analysis on ERC data.`),
  P(`Geography is the larger disparity by an order of magnitude. A widening-country share of 4% against a population share of 25%, and success-rate ratios of 0.25–0.40 under any plausible applicant share (0.34 at the 11% share of applications the ERC reports for 2024), dwarf the gender contrast; the ERC's own white paper attributes this to structural conditions in host institutions ${c("erc_white")}, a claim that can only be tested with the unpublished per-call applicant denominators by country. The association-status analysis adds a second finding: the UK's loss of roughly one-third of its hosted StGs during non-association has persisted for three calls after re-association, and the portfolio re-concentrated in Germany. Whether UK-based applicants stopped applying, moved, or lost at evaluation is again a question for applicant-level data.`),
  P("The competition-dynamics results reframe the fairness debate. The same proposal faces odds of success that differ by up to 1.85-fold between calls purely because demand and budgets move; demand does not self-correct when success rates fall, so the deadweight cost of unfunded proposals grows mechanically—one to two and a half person-years per grant in 2026. Cohort luck of this size is larger than any gender or domain effect we measured. The domain analysis shows a rule that works as intended (budget-proportional allocation equalises success rates) while allowing the disciplinary composition of the portfolio to drift with application behaviour, SH having gained ten percentage points of the pool since 2013 without an explicit decision."),
  H("5.2 Comparison with quasi-experimental evidence on what the grant does", 2),
  P(`The only ERC-wide causal study, a multi-cutoff regression discontinuity on all 2007–2013 applicants, finds no significant effect of winning on productivity or quality near the threshold, with a possible exception in physics Starting Grants ${c("ghirelli")}. Near-miss studies at the NIH show that a narrow rejection raises attrition by more than ten percentage points but that those who persist produce more highly cited work ${c("wang")}, and studies of the Matthew effect show that early wins compound into later funding partly because near-losers stop applying ${c("bol")}. Together with the marginal effects reported for NIH R01 awards ${c("jacob")}, this literature implies that the marginal StG grant buys little measurable output but shapes careers through retention and cumulative advantage—precisely the channel through which cohort luck and geographic concentration become permanent. The debate about "private versus public" funding is, in these terms, a debate about horizon, tolerance of failure and people-versus-project focus: HHMI investigators produce high-impact papers at a much higher rate than matched NIH-funded scientists ${c("azoulay")}, and the ERC itself is a public scheme built on the HHMI template.`),
  H("5.3 Policy implications", 2),
  ...numbered([
    "**Publish the denominators.** Applicant counts by gender × domain and by host country per call would resolve, at negligible cost, the two identification problems that dominate this paper (domain-specific gender effects; geographic success-rate ratios). Applicant-level pre-application productivity, available inside the ERC, would identify the self-selection differential.",
    "**Stabilise the success rate.** Multi-year budget smoothing or a cap on resubmissions would reduce cohort luck and the application tax more cheaply than any reform of the evaluation itself; the 2026 call shows what an unmanaged demand shock costs.",
    "**Keep the second stage; consider a hybrid lottery for the middle of the ranking.** The two-stage design is worth about 0.13 SD of funded merit for 70% fewer full reviews. A merit-top-half-plus-lottery would cost about 0.12 SD and modestly compress disparity amplification; a full threshold lottery would cost 0.30 SD. The choice is a value judgement about merit versus equity and transparency, but the terms of trade are now quantified.",
    "**Treat the geographic gradient as the primary equity problem.** Parity for widening countries at plausible applicant shares would require 6–11% of grants to move; measures that raise the applicant pool (mentoring, visiting fellowships) address the larger of the two components if the applicant share is indeed 10–15%.",
    "**Monitor the disciplinary drift.** If budget-proportional allocation is to remain the rule, the Scientific Council should at least make the resulting shift towards SH visible and deliberate.",
    "**Interpret gender statistics with the estimand in view.** Annual reporting of women's success rates should be accompanied by the applicant-pool composition and, ideally, by a self-selection-adjusted range rather than a single number.",
  ]),
  H("5.4 Limitations", 2),
  ...bullets([
    "Applicant gender is taken from rounded shares and, for 2026, from secondary reporting; the rounding is propagated, but the applicant pool is assumed to contain negligible numbers of non-binary applicants.",
    "Grant counts differ between initial and reserve-list releases (2021: 397 versus 471; 2023: 400 versus 398); the version with the gender split is used, with a sensitivity check.",
    "The historical comparator is an aggregate of rounded rates; the 2013, 2015 and 2016 applicant shares are imputed; grant counts for 2007–2012 and 2014 in the competition series are recalled rather than re-verified, and the verified thirteen-call series drives the main estimates.",
    "The domain-composition adjustment relies on assumed within-domain shares; no applicant counts by country exist, so the geographic success-rate ratio and the association contrasts are scenario-based or descriptive.",
    "The application-cost figures rest on an external per-proposal time estimate (20–50 working days) and are order-of-magnitude numbers; the parity projection is a linear extrapolation over a ten-call window.",
    "The reliability meta-analysis has k = 3 with one dominant study, and the between-funder SD used in propagation is an assumption; the selection simulator is a stylised model (normal merit, independent stage errors, fixed pool multiplier) whose value lies in the ordering of mechanisms and their sensitivity to reliability, not in the absolute numbers.",
    "Literature estimates quoted for context are as reported by their authors; two commonly cited figures are marked in the evidence map as not re-verified.",
  ]),
  H("5.5 Research agenda", 2),
  P("Fourteen meta-analytic questions follow directly from these results and are set out with estimands, data sources, identification strategies and biases in the supplementary policy agenda: the local causal effect of winning a StG by panel and career stage; breakthrough rates in the ERC's ex-post evaluations; the elasticity of output to grant size; the reliability of the two-step evaluation and the incremental value of the interview; lotteries versus panels in the trials now running at several funders; applicant-pool dynamics and the application tax; gender treatment net of self-selection; geographic disadvantage decomposed into pool and evaluation components; association status as a natural experiment; mobility; public versus philanthropic funding designs; grant size and duration; the welfare cost of low success rates; and grant conditions. The single parameter that links most of them is the reliability of the evaluation stage."),
  H("6. Conclusions", 1),
  P("Pooling ten ERC Starting Grant calls shows that women have been funded at least as often as men since 2017, with a small and stable advantage that reverses the FP7-era deficit; that this parity is compatible with neutral, favourable or unfavourable treatment at the evaluation stage because self-selection is unobserved; that the geographic gradient is an order of magnitude larger and persistent; that framework association has durable effects on where grants are hosted; that cohort luck and application cost are first-order inefficiencies which demand does not correct; that domain success rates are equalised by design while the portfolio drifts with demand; and that the reliability of peer review, estimated at 0.26 per rater and about 0.64 for a five-rater panel, sets the price of every reform. The ERC could resolve most of the remaining ambiguity by publishing applicant denominators by gender, domain and country and by opening applicant-level data to independent quasi-experimental analysis."),
  H("Data and code availability", 1),
  P("All inputs are public ERC documents whose URLs are listed in Supplementary Table S1b and in the evidence map. The analysis code (Python package erc_meta with modules data, core, bayes, bias, geo, dynamics, domains, policy, plots and the pipeline run_all.py), the extracted data, all 26 tables, 15 figures and a machine-readable results file are provided as supplementary material; a single command regenerates everything."),
  H("Declarations", 1),
  P("**Author contributions.** [To be completed by the authors.]", { align: AlignmentType.LEFT }),
  P("**Competing interests.** [To be declared by the authors.]", { align: AlignmentType.LEFT }),
  P("**Funding.** No dedicated funding was received for this analysis; all inputs are public ERC documents.", { align: AlignmentType.LEFT }),
  P("**Ethics.** The study uses only aggregate, publicly published statistics; no individual-level or confidential data were accessed.", { align: AlignmentType.LEFT }),
  H("Declaration of generative AI and AI-assisted technologies in the manuscript preparation process", 2),
  P("During the preparation of this work, the authors used Claude (Anthropic; Claude 5-family model, claude.ai) for drafting the manuscript text and for drafting and streamlining the analysis code. The authors reviewed and edited the output as needed and take full responsibility for the content of the published article.", { align: AlignmentType.JUSTIFIED }),
  H("References", 1),
  ...refList(refs),
];

// ----------------------------------------------------------------------------- build main document
const A4 = { width: 11906, height: 16838 };
const mainDoc = new Document({
  creator: "erc_meta pipeline", title: title, styles, numbering,
  sections: [{
    properties: { page: { size: A4, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    footers: { default: footer("ERC Starting Grants: call-level meta-analysis") },
    children: [
      new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 30, color: "1F3864" })], alignment: AlignmentType.LEFT, spacing: { after: 200 } }),
      ...authorBlock(),
      P("Manuscript prepared 22 September 2026; data extracted and analyses run 6 September 2026. Reproducible pipeline: erc_stg_meta v1.0 (supplementary material).", { align: AlignmentType.LEFT, run: { size: 18, italics: true }, after: 200 }),
      H("Abstract", 1),
      ...abstract,
      pageBreak(),
      ...intro, ...data, ...methods, ...results, ...discussion,
    ],
  }],
});

// ----------------------------------------------------------------------------- supplementary document
const S = TABLES.supp;
const suppOrder = ["s1", "s1b", "s2", "s3", "s3b", "s4", "s5", "s5b", "s6", "s6b", "s7", "s8", "s9", "s10", "s11", "s11b", "s11c", "s12", "s12b", "s12c", "s12d", "s12e", "s13", "s13b", "s14", "s14b", "s15", "s15b"];
const LAND_TOTAL = 14600;
const suppMethods = [
  H("Supplementary Methods: formulas", 1),
  P("Effect sizes. For a call with a women funded, b women not funded, c men funded and d men not funded: log OR = ln(ad/bc), Var = 1/a + 1/b + 1/c + 1/d; log RR = ln[(a/(a+b))/(c/(c+d))], Var = 1/a − 1/(a+b) + 1/c − 1/(c+d); RD = a/(a+b) − c/(c+d) with the binomial variance.", { align: AlignmentType.LEFT }),
  P("Pooling. Common effect: weights w = 1/v. Random effects: w* = 1/(v + τ²). DerSimonian–Laird τ² = max{0, (Q − (k−1))/C}, C = Σw − Σw²/Σw. Paule–Mandel: τ² solving Q(τ²) = k − 1. REML: τ² maximising −½Σln(v+τ²) − ½ln Σw* − ½Σw*(y − ȳ)². Q-profile interval for τ²: {τ²: χ²(k−1; 0.025) ≤ Q(τ²) ≤ χ²(k−1; 0.975)}. Hartung–Knapp: SE = √[Σw*(y−ȳ)²/((k−1)Σw*)] with t(k−1) quantiles. Prediction interval: ȳ ± t(k−2; 0.975)√(τ² + SE²). Mantel–Haenszel OR = ΣR/ΣS with R = ad/n, S = bc/n and the Robins–Breslow–Greenland variance.", { align: AlignmentType.LEFT }),
  P("Meta-regression. y = Xβ + u + e, u ~ N(0, τ²), e ~ N(0, v); REML τ²; Knapp–Hartung variance (X′WX)⁻¹·QE/(k − p); permutation test by permuting the moderator across calls.", { align: AlignmentType.LEFT }),
  P("Exact-conditional model. Given margins (n_w, n_m, g), P(A = a | θ) ∝ C(n_w, a)C(n_m, g−a)exp(aθ); the marginal likelihood ∫P(a|θ)N(θ; μ, τ²)dθ was evaluated on a θ grid of 2,001 points and the posterior on a 321 × 161 (μ, τ) grid; Savage–Dickey BF₀₁ = p(μ = 0 | data)/p(μ = 0).", { align: AlignmentType.LEFT }),
  P("Bias analysis. Domain confounding: with domain success rates r_d and within-domain women's shares s_d, E[p_w] = Σs_d n_d r_d / Σs_d n_d and E[p_m] = Σ(1−s_d)n_d r_d / Σ(1−s_d)n_d; OR_conf = odds(E[p_w])/odds(E[p_m]). E-value = RR + √[RR(RR−1)]. Self-selection: with score SD s = ρ^−½, p_w = Φ[(δ − t)/s], p_m = Φ(−t/s), t solving w·p_w + (1−w)·p_m = success rate; OR_fair = odds(p_w)/odds(p_m).", { align: AlignmentType.LEFT }),
  P("Geography. Widening share pooled on the logit scale; standardised grant ratio = observed/(total × assumed applicant share) with Garwood intervals; implied success-rate ratio = [s_g/s_a]/[(1−s_g)/(1−s_a)] for grant share s_g and applicant share s_a.", { align: AlignmentType.LEFT }),
  P("Dynamics. Cohort OR between calls A and B = odds(SR_A)/odds(SR_B); Δlog SR = Δlog G − Δlog N; elasticity from OLS of Δlog N_t on Δlog SR_{t−1} with HC1 errors; application cost = N × days/220.", { align: AlignmentType.LEFT }),
  P("Selection simulation. Merit Q ~ N(0,1) (+δ for the subgroup); score = Q + ε with Var(ε) = (1−ρ)/ρ; two-stage reliability 2ρ/(1+ρ); Spearman–Brown for r raters: rρ₁/(1 + (r−1)ρ₁).", { align: AlignmentType.LEFT }),
  H("Supplementary Code", 1),
  P("The analysis package erc_meta (Python ≥ 3.10; numpy, scipy, pandas, matplotlib) contains: data.py (inputs with provenance; 2×2 construction; host-country counts; competition series), core.py (effect sizes; IV/MH/Peto; DL/PM/REML; Q-profile and I² intervals; HKSJ; prediction intervals; meta-regression with permutation tests; leave-one-out, cumulative and Baujat diagnostics; Egger, Peters, Begg; trim-and-fill; PET-PEESE; limit meta-analysis), bayes.py (grid posteriors for the normal–normal and exact-conditional models; priors; Bayes factors; posterior predictive; power priors), bias.py (E-values; probabilistic bias analysis; self-selection model), geo.py (widening share; standardised grant ratios; concentration; country shares; association contrasts; rank stability; reallocation), dynamics.py (success-rate meta-analysis; decomposition; elasticity; application cost; women's share trend), domains.py (neutrality tests; rate ratios; share trends; gender × domain bounds), policy.py (selection simulator; dispersal curve; reliability meta-analysis and propagation) and plots.py. The pipeline run_all.py regenerates every table, figure and results.json in about two minutes; prepare_tables.py and make_paper.js build this paper and supplement from those outputs. The full source is distributed as erc_stg_meta_analysis.zip.", { align: AlignmentType.LEFT }),
];
const suppFigs = [
  H("Supplementary Figures", 1),
  ...figure(path.join(FIG, "fig03_cumulative_loo.png"), "**Figure S1.** Cumulative meta-analysis by call year (left) and leave-one-out influence (right).", 860),
  ...figure(path.join(FIG, "fig04_funnel_baujat.png"), "**Figure S2.** Contour-enhanced funnel plot with Egger regression line and trim-and-fill imputation (left) and Baujat plot (right).", 860),
  ...figure(path.join(FIG, "fig05_metaregression_year.png"), "**Figure S3.** Mixed-effects meta-regression of the log OR on call year with Knapp–Hartung band.", 760),
  ...figure(path.join(FIG, "fig10_extended_series.png"), "**Figure S4.** Extended series including the 2013, 2015 and 2016 calls with imputed applicant shares (grey), the primary and extended pooled intervals, and the FP7-era comparator.", 820),
  ...figure(path.join(FIG, "fig02_success_rates.png"), "**Figure S5.** Success rates by gender per call (also shown as Figure 2 of the main text).", 860),
];
const suppTables = [];
suppOrder.forEach(k => { suppTables.push(...makeTable(S[k], { total: LAND_TOTAL })); });

const suppDoc = new Document({
  creator: "erc_meta pipeline", title: "Supplementary Data", styles, numbering,
  sections: [
    {
      properties: { page: { size: A4, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      footers: { default: footer("Supplementary data") },
      children: [
        new Paragraph({ children: [new TextRun({ text: "Supplementary Data", bold: true, size: 30, color: "1F3864" })], spacing: { after: 120 } }),
        new Paragraph({ children: [new TextRun({ text: title, size: 22, italics: true })], spacing: { after: 160 } }),
        ...authorBlock(18),
        new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: "" })] }),
        P("Contents: Supplementary Methods (formulas); Supplementary Code description; Supplementary Figures S1–S5; Supplementary Tables S1–S15b (every table produced by the analysis pipeline, including full provenance with source URLs, the evidence map and the complete simulation grids).", { align: AlignmentType.LEFT }),
        ...suppMethods,
        ...suppFigs,
      ],
    },
    {
      properties: { page: { size: { width: A4.width, height: A4.height, orientation: PageOrientation.LANDSCAPE }, margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } },
      footers: { default: footer("Supplementary tables") },
      children: [H("Supplementary Tables", 1), ...suppTables],
    },
  ],
});

(async () => {
  fs.mkdirSync(OUTDIR, { recursive: true });
  fs.writeFileSync(path.join(OUTDIR, "ERC_StG_meta_analysis_paper.docx"), await Packer.toBuffer(mainDoc));
  fs.writeFileSync(path.join(OUTDIR, "ERC_StG_meta_analysis_supplementary_data.docx"), await Packer.toBuffer(suppDoc));
  console.log("written");
})();
