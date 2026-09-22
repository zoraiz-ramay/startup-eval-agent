"""Siemens program eligibility: what Connect, Collaborate and Empower actually require, and
when Siemens Financial Services is a real avenue rather than a reflex.

This module is a CATALOGUE plus pure predicates over an evaluated profile — the same shape as
`siemens_tools.csv`, and deliberately not part of `route.py`, which stays about routing. It
imports nothing from `api/` and performs no I/O: everything it reads was gathered upstream.

Why it exists
-------------
The routing gates were numeric thresholds over the six scoring dimensions, which encode how
*good* a startup looks but not whether Siemens' published programs would actually take it. Across
the 18 runs stored when this was written, the consequence was stark: `Empower` was appended with
no gate at all, so the answer was only ever Empower or Pass; `secondary` was empty in every single
run; and the SFS flag was true 18 times out of 18, because the extraction asked whether the
startup sat in a capital-intensive space and the model answered about the startup's CUSTOMERS.

Siemens publishes real criteria for all four, and they are checkable. Encoding them turns a score
comparison into a decision a reviewer can audit, argue with, and hand back to a founder as a list
of things to go and prove.

Three outcomes, not two
-----------------------
The distinction that carries most of the value here is between a pillar that is WRONG for a
company and one that is merely UNPROVEN:

* ``blocked``  — a blocking criterion failed. Something about the company makes this pillar the
  wrong answer, and no amount of further evidence changes that. A product that substitutes a
  Siemens tool cannot be listed beside it on the Marketplace as a partner offering.
* ``unproven`` — nothing disqualifies it, but a required criterion is unmet or unevidenced. This
  is the common case, and it is actionable: ``next_steps`` says exactly what would have to be
  shown.
* ``eligible`` — every required criterion is met.

Reporting both failures as "no" is what a threshold does, and it is the less useful half of the
answer.
"""
from __future__ import annotations

import re

import pandas as pd

# Sources for every criterion below, cited so a reviewer can check the rule rather than trust it.
SOURCES = {
    "programs": "https://www.siemens.com/en-us/company/innovation/startups/",
    "connect": "https://www.siemens.com/en-us/company/innovation/startups/connect/",
    "collaborate": "https://www.siemens.com/en-us/company/innovation/startups/collaborate/",
    "empower": "https://www.siemens.com/en-us/startups/empower/",
    "marketplace_governance": "https://developer.siemens.com/guidelines/architecture-external/index.html",
    "become_a_seller": "https://www.siemens.com/en-us/ecosystem/become-a-seller/",
    "sfs": "https://www.siemens.com/en-us/company/about/businesses/financial-services/",
    "sfs_equipment": "https://www.siemens.com/en-us/products/financial-services/equipment-technology-finance/",
}

PILLARS = ("Connect", "Collaborate", "Empower")

# ---------------------------------------------------------------------- Collaborate domains
# Siemens names five innovation domains on the Collaborate page and takes applications per domain,
# so a startup outside all five is not being turned down on quality — it is outside the stated
# scope of the programme, which is a different and much more useful thing to tell a reviewer.
COLLABORATE_DOMAINS = {
    "ar_vr": {
        "label": "Augmented and virtual reality",
        "note": "training, assembly support, remote commissioning",
        "terms": (r"augmented realit", r"virtual realit", r"mixed realit", r"\bxr\b", r"\bar/vr\b",
                  r"\bhead(?:set|-mounted)", r"remote commissioning", r"immersive",
                  r"assembly support", r"spatial comput"),
    },
    "ai_data": {
        "label": "AI and data analytics",
        "note": "digital twins, data cleansing, pattern recognition",
        "terms": (r"\bartificial intelligence\b", r"\bmachine learning\b", r"\bdeep learning\b",
                  r"\bcomputer vision\b", r"\banalytics\b", r"\bdigital twin", r"\bllm\b",
                  r"\bgenerative ai\b", r"pattern recognit", r"data cleans", r"predictive",
                  r"\bforecast", r"\bdata platform\b", r"\bneural\b"),
    },
    "automation": {
        "label": "Automation",
        "note": "flexible, human-collaborative manufacturing",
        "terms": (r"\brobot", r"\bcobot\b", r"\bautomation\b", r"\bautomated\b", r"\bplc\b",
                  r"motion control", r"pick[- ]and[- ]place", r"assembly line",
                  r"\bmachine tending\b", r"flexible manufactur", r"\bcnc\b", r"\bagv\b",
                  r"\bamr\b", r"\bactuator"),
    },
    "energy_infra": {
        "label": "Sustainable energy and infrastructure",
        "note": "grid optimization, decarbonization",
        "terms": (r"\bgrid\b", r"decarbon", r"\brenewable", r"energy storage", r"\bbattery\b",
                  r"\bhydrogen\b", r"\bsolar\b", r"\bwind (?:farm|turbine|power)",
                  r"heat pump", r"\bcharging\b", r"\bev charg", r"power electronic",
                  r"\bemission", r"\brecycl", r"circular econom", r"\bwater treatment\b",
                  r"building efficien", r"\bhvac\b", r"\bmicrogrid\b"),
    },
    "connectivity_iot": {
        "label": "Connectivity, IoT and Edge",
        "note": "asset performance and operational efficiency",
        "terms": (r"\biot\b", r"\biiot\b", r"\bedge comput", r"\bedge device", r"\bsensor",
                  r"\btelemetry\b", r"\b5g\b", r"\bopc ua\b", r"\bmqtt\b", r"\bgateway\b",
                  r"condition monitor", r"asset performance", r"\bconnectivity\b",
                  r"predictive maintenance", r"\bscada\b", r"\bot network"),
    },
}

# ---------------------------------------------------------------------- Empower bundles
# The Siemens Xcelerator software the Empower programme actually packages for startups, mapped to
# the kind of building each one accelerates. Naming the bundle is the difference between telling a
# founder "you qualify for Empower" and telling them "Solid Edge is free for a year, and NX and
# Simcenter are up to 90% off".
EMPOWER_BUNDLES = (
    {"id": "mechanical", "label": "NX CAD / Solid Edge",
     "offer": "Solid Edge is a one-year free licence; NX is discounted up to 90%",
     "terms": (r"\bcad\b", r"mechanical design", r"\bpart design\b", r"product design",
               r"\bassembl", r"sheet metal", r"machine design", r"\benclosure\b",
               r"\bmechatronic", r"industrial design", r"\bprototyp")},
    {"id": "simulation", "label": "Simcenter 3D / 1D / STAR-CCM+",
     "offer": "discounted simulation across structural, system and CFD",
     "terms": (r"\bsimulation\b", r"\bcfd\b", r"\bfea\b", r"finite element", r"fluid dynamic",
               r"\bthermal\b", r"\bstructural\b", r"\baerodynamic", r"\bmodel(?:ling|ing)\b",
               r"digital twin", r"\bprocess model")},
    {"id": "electronics", "label": "PADS Professional",
     "offer": "PCB schematic and layout design",
     "terms": (r"\bpcb\b", r"printed circuit", r"\bschematic\b", r"\belectronics\b",
               r"\bcircuit\b", r"board design", r"embedded hardware", r"\bsemiconductor\b",
               r"\bchip\b", r"\bsilicon\b")},
    {"id": "plm", "label": "Teamcenter",
     "offer": "product lifecycle and BOM management",
     "terms": (r"\bplm\b", r"\bbom\b", r"bill of materials", r"product lifecycle",
               r"configuration management", r"engineering data")},
    {"id": "lowcode", "label": "Mendix",
     "offer": "low-code application platform",
     "terms": (r"\blow[- ]code\b", r"\bworkflow\b", r"\bweb app", r"internal tool",
               r"\bsoftware platform\b", r"\bdashboard", r"\bsaas\b", r"\bapplication\b")},
    {"id": "frontier", "label": "Frontier developer licences",
     "offer": "a year of free developer licences (additive, AR/VR, robotics, industrial AI)",
     "terms": (r"additive manufactur", r"3d print", r"\brobot", r"augmented realit",
               r"virtual realit", r"industrial ai", r"\bmachine learning\b",
               r"\bcomputer vision\b")},
)

# Reads as a services business rather than a product company. Empower packages software for people
# who are BUILDING something; a consultancy has nothing for the licence to accelerate.
_SERVICES_ONLY = re.compile(
    r"\bconsultanc|\bconsulting firm\b|\bstaffing\b|\bagency\b|\bsystem integrator\b|"
    r"\boutsourc|\bbody shop\b|\brecruit(?:ment|ing)\b|\bmarketing services\b", re.I)

# Certifications the Marketplace governance names by name. SOC 2 and the rest are real assurance
# but are not what the requirement asks for, so they are reported as progress, not as compliance.
_MARKETPLACE_CERTS = ("ISO/IEC 27001", "IEC 62443")


# ====================================================================== helpers

def _txt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def _startup_text(row: pd.Series, profile: dict, fit: dict) -> str:
    """Everything the run knows about what the company does, as one lowercase blob.

    The fit stage's derived keywords are included: they are the model's own reading of the
    startup's capability space, and they routinely name a technology the pitch text only implies.
    """
    parts = [_txt(row.get(c, "")) for c in
             ("company_name", "short_description", "Your pitch", "Business model",
              "Differentiation", "Development stage of your solution", "about_enriched")]
    parts.append(_txt(profile.get("customer_segment", "")))
    parts.extend(str(k) for k in (fit.get("keywords") or []))
    parts.extend(str(m.get("rationale", "")) for m in (fit.get("matches") or []))
    return " ".join(p for p in parts if p).lower()


def _headcount(row: pd.Series, profile: dict) -> int:
    text = _txt(row.get("employees_count", "")) or _txt(row.get("employee_band", "")) \
        or _txt(profile.get("employees", ""))
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]
    return int(min(nums)) if nums else 0


def _commercial(profile: dict) -> dict:
    return profile.get("commercial") or {}


def _top_relation(fit: dict) -> str:
    matches = fit.get("matches") or []
    return str(matches[0].get("relation", "")).strip().lower() if matches else ""


def _top_division(fit: dict) -> str:
    matches = fit.get("matches") or []
    return str(matches[0].get("division", "")).strip() if matches else ""


def _match(blob: str, terms) -> bool:
    return any(re.search(t, blob, re.I) for t in terms)


def _c(cid, label, status, note="", evidence_url="", required=True, blocking=False) -> dict:
    """One criterion outcome. ``status`` is met | unmet | unknown."""
    return {"id": cid, "label": label, "status": status, "note": note,
            "evidence_url": evidence_url, "required": required, "blocking": blocking}


def classify_collaborate_domains(row: pd.Series, profile: dict, fit: dict) -> list[dict]:
    """Which of Siemens' five published innovation domains this startup falls in."""
    blob = _startup_text(row, profile, fit)
    return [{"id": did, "label": d["label"], "note": d["note"]}
            for did, d in COLLABORATE_DOMAINS.items() if _match(blob, d["terms"])]


def match_empower_bundles(row: pd.Series, profile: dict, fit: dict) -> list[dict]:
    """Which Siemens Xcelerator startup bundles would accelerate what this company builds."""
    blob = _startup_text(row, profile, fit)
    return [{"id": b["id"], "label": b["label"], "offer": b["offer"]}
            for b in EMPOWER_BUNDLES if _match(blob, b["terms"])]


# ====================================================================== pillar assessment

def _empower_criteria(row, profile, fit, score) -> tuple[list[dict], dict]:
    commercial = _commercial(profile)
    blob = _startup_text(row, profile, fit)
    headcount = _headcount(row, profile)
    stage = str(commercial.get("funding_stage") or "")
    bundles = match_empower_bundles(row, profile, fit)
    out = []

    # Empower is explicitly "for early-stage innovators". A scaled company is not being judged
    # unworthy; it is past the programme, which is why this is blocking rather than merely unmet.
    if headcount >= 250 or stage == "series_b_plus":
        out.append(_c("early_stage", "Early-stage company", "unmet",
                      f"Reads as a scaled venture ({headcount or '?'} staff"
                      f"{', ' + stage.replace('_', ' ') if stage else ''}) — Empower targets "
                      "early-stage innovators.", SOURCES["empower"], blocking=True))
    elif headcount and headcount < 50 or stage in ("pre_seed", "seed", "grant") \
            or score.get("dimensions", {}).get("product", 100) <= 75:
        out.append(_c("early_stage", "Early-stage company", "met",
                      f"{headcount} staff" if headcount else
                      (stage.replace("_", " ") if stage else "early product stage"),
                      SOURCES["empower"], blocking=True))
    else:
        out.append(_c("early_stage", "Early-stage company", "unknown",
                      "No headcount, funding stage or product stage evidenced.",
                      SOURCES["empower"], blocking=True))

    if _SERVICES_ONLY.search(blob):
        out.append(_c("builds_a_product", "Builds a product, not a service", "unmet",
                      "Reads as a consultancy or services business — Empower packages software "
                      "for companies building something with it.", SOURCES["empower"],
                      blocking=True))
    else:
        out.append(_c("builds_a_product", "Builds a product, not a service", "met", "",
                      SOURCES["empower"], blocking=True))

    if bundles:
        out.append(_c("bundle_match", "A Siemens Xcelerator bundle fits the build", "met",
                      "; ".join(f"{b['label']} — {b['offer']}" for b in bundles[:3]),
                      SOURCES["empower"]))
    else:
        out.append(_c("bundle_match", "A Siemens Xcelerator bundle fits the build", "unmet",
                      "Nothing in the startup's description maps to NX, Simcenter, Teamcenter, "
                      "Solid Edge, Mendix, PADS or the Frontier track.", SOURCES["empower"]))

    return out, {"bundles": bundles}


def _connect_criteria(row, profile, fit, score) -> tuple[list[dict], dict]:
    """The Xcelerator Marketplace publishes its seller governance, so these are real gates.

    A note on strictness: the certification and API requirements are things a startup can go and
    ACQUIRE, so failing them is a next step, not a disqualification. Being a substitute for a
    Siemens product is not acquirable — it is what the company is — so that one blocks.
    """
    commercial = _commercial(profile)
    relation = _top_relation(fit)
    certs = [c.get("name") for c in commercial.get("certifications", []) if isinstance(c, dict)]
    marketplace_certs = [c for c in certs if c in _MARKETPLACE_CERTS]
    traction = score.get("dimensions", {}).get("traction", 0)
    headcount = _headcount(row, profile)
    revenue = str(commercial.get("revenue_signal") or "")
    out = []

    if relation == "substitute":
        out.append(_c("not_a_substitute", "Complements rather than replaces Siemens software",
                      "unmet", "The closest portfolio match is classified a substitute — a "
                      "competing product cannot be listed beside it as a partner offering.",
                      SOURCES["connect"], blocking=True))
    elif relation in ("complement", "integration", "adjacent"):
        out.append(_c("not_a_substitute", "Complements rather than replaces Siemens software",
                      "met", f"Closest portfolio match is classified {relation}.",
                      SOURCES["connect"], blocking=True))
    else:
        out.append(_c("not_a_substitute", "Complements rather than replaces Siemens software",
                      "unknown", "No portfolio relation was established.", SOURCES["connect"],
                      blocking=True))

    deployment = str(commercial.get("deployment") or "")
    if deployment in ("cloud", "edge"):
        out.append(_c("cloud_or_edge", "Cloud and/or edge, delivered as a service", "met",
                      f"Evidenced as {deployment}.", commercial.get("deployment_source", ""),
                      ))
    elif deployment in ("on_prem", "hardware"):
        out.append(_c("cloud_or_edge", "Cloud and/or edge, delivered as a service", "unmet",
                      f"Evidenced as {deployment.replace('_', '-')}. Marketplace offerings must "
                      "be cloud and/or edge with automated deployment and operations.",
                      commercial.get("deployment_source", "")))
    else:
        out.append(_c("cloud_or_edge", "Cloud and/or edge, delivered as a service", "unknown",
                      "Deployment model not evidenced.", SOURCES["marketplace_governance"]))

    if commercial.get("has_public_api"):
        out.append(_c("api_exposed", "Functionality exposed through APIs", "met", "",
                      commercial.get("api_source", "")))
    else:
        out.append(_c("api_exposed", "Functionality exposed through APIs", "unknown",
                      "No developer documentation, API reference or SDK found.",
                      SOURCES["marketplace_governance"]))

    if marketplace_certs:
        out.append(_c("security_certified", "ISO/IEC 27001 or IEC 62443", "met",
                      ", ".join(marketplace_certs),
                      next((c.get("source_url", "") for c in commercial.get("certifications", [])
                            if isinstance(c, dict) and c.get("name") in _MARKETPLACE_CERTS), "")))
    elif certs:
        out.append(_c("security_certified", "ISO/IEC 27001 or IEC 62443", "unmet",
                      f"Holds {', '.join(certs)}, which is real assurance but not what the "
                      "Marketplace governance names.", SOURCES["marketplace_governance"]))
    else:
        out.append(_c("security_certified", "ISO/IEC 27001 or IEC 62443", "unknown",
                      "No security certification evidenced.", SOURCES["marketplace_governance"]))

    if commercial.get("pricing_public") or revenue in ("recurring", "contracted"):
        out.append(_c("purchasable", "A buyable offering, not a bespoke engagement", "met",
                      "Published pricing." if commercial.get("pricing_public")
                      else f"Revenue evidenced as {revenue}.",
                      commercial.get("pricing_source") or commercial.get("revenue_source", "")))
    else:
        out.append(_c("purchasable", "A buyable offering, not a bespoke engagement", "unknown",
                      "No published price, plan tier or contracted revenue found.",
                      SOURCES["become_a_seller"]))

    # Connect addresses mature ventures. Kept as a required criterion rather than a blocker: a
    # young company can grow into it, and the reviewer wants to know it is the gap.
    if traction >= 35 or revenue in ("recurring", "contracted") or headcount >= 25:
        out.append(_c("mature_venture", "Mature enough to sell through a global channel", "met",
                      f"traction {traction}"
                      + (f", {headcount} staff" if headcount else ""), SOURCES["connect"]))
    else:
        out.append(_c("mature_venture", "Mature enough to sell through a global channel", "unmet",
                      f"traction {traction} with no contracted revenue — Connect addresses "
                      "mature ventures.", SOURCES["connect"]))

    return out, {"identity_federation_note":
                 "SiemensID federation for SSO is mandatory for every seller application and is "
                 "an onboarding step, not something the open web can evidence."}


def _collaborate_criteria(row, profile, fit, score) -> tuple[list[dict], dict]:
    commercial = _commercial(profile)
    relation = _top_relation(fit)
    division = _top_division(fit)
    domains = classify_collaborate_domains(row, profile, fit)
    product = score.get("dimensions", {}).get("product", 0)
    headcount = _headcount(row, profile)
    out = []

    if domains:
        out.append(_c("innovation_domain", "Falls in a named Collaborate domain", "met",
                      "; ".join(f"{d['label']} ({d['note']})" for d in domains),
                      SOURCES["collaborate"], blocking=True))
    else:
        out.append(_c("innovation_domain", "Falls in a named Collaborate domain", "unmet",
                      "Outside all five domains Siemens takes Collaborate applications for: "
                      "AR/VR, AI and data analytics, automation, sustainable energy and "
                      "infrastructure, connectivity/IoT/Edge.", SOURCES["collaborate"],
                      blocking=True))

    if relation == "substitute":
        out.append(_c("complementary", "Brings capability Siemens does not have", "unmet",
                      "Classified a substitute — Siemens co-develops what it lacks, and buys "
                      "early from startups that extend the portfolio rather than duplicate it.",
                      SOURCES["collaborate"], blocking=True))
    elif relation in ("complement", "integration"):
        out.append(_c("complementary", "Brings capability Siemens does not have", "met",
                      f"Classified {relation}.", SOURCES["collaborate"], blocking=True))
    elif relation == "adjacent":
        out.append(_c("complementary", "Brings capability Siemens does not have", "unknown",
                      "Classified adjacent — same domain, different function. Needs a human "
                      "read on whether it extends the portfolio.", SOURCES["collaborate"],
                      blocking=True))
    else:
        out.append(_c("complementary", "Brings capability Siemens does not have", "unknown",
                      "No portfolio relation was established.", SOURCES["collaborate"],
                      blocking=True))

    # Siemens becomes an early CUSTOMER, so there has to be something to buy and pilot.
    if product >= 55 or score.get("verified_customers", 0):
        out.append(_c("pilot_ready", "Technology mature enough to pilot", "met",
                      f"product {product}"
                      + (f", {score['verified_customers']} corroborated customer(s)"
                         if score.get("verified_customers") else ""),
                      SOURCES["collaborate"]))
    else:
        out.append(_c("pilot_ready", "Technology mature enough to pilot", "unmet",
                      f"product {product} — below a working prototype in a real environment.",
                      SOURCES["collaborate"]))

    if division:
        out.append(_c("bu_sponsor", "A plausible sponsoring business unit", "met",
                      f"Closest portfolio match sits in {division}.", SOURCES["collaborate"]))
    else:
        out.append(_c("bu_sponsor", "A plausible sponsoring business unit", "unknown",
                      "No Siemens division identified from the portfolio match.",
                      SOURCES["collaborate"]))

    # A venture-client engagement means an enterprise procurement cycle and a co-development
    # commitment. A two-person pre-revenue team is a real risk to both sides, not a slight.
    if headcount >= 5 or commercial.get("funding_stage") in ("seed", "series_a", "series_b_plus"):
        out.append(_c("can_deliver", "Able to carry an enterprise engagement", "met",
                      f"{headcount} staff" if headcount else
                      str(commercial.get("funding_stage", "")).replace("_", " "),
                      SOURCES["collaborate"], required=False))
    else:
        out.append(_c("can_deliver", "Able to carry an enterprise engagement", "unknown",
                      "Team size and funding stage not evidenced — a venture-client engagement "
                      "runs on a Siemens procurement cycle.", SOURCES["collaborate"],
                      required=False))

    return out, {"domains": domains, "division": division}


_PILLAR_BUILDERS = {
    "Empower": _empower_criteria,
    "Connect": _connect_criteria,
    "Collaborate": _collaborate_criteria,
}


def assess_pillar(pillar: str, row: pd.Series, profile: dict, fit: dict,
                  score: dict) -> dict:
    """Evaluate one pillar's published criteria against an evaluated startup.

    Returns ``{pillar, status, eligible, criteria, blockers, next_steps, detail}`` where status is
    ``eligible`` | ``unproven`` | ``blocked``. Never raises: a criteria builder that trips on
    unexpected data yields ``unproven`` with the reason, because silently reporting a pillar as
    ineligible is exactly the failure this module was written to remove.
    """
    row = row if row is not None else pd.Series(dtype=str)
    profile, fit, score = profile or {}, fit or {}, score or {}
    builder = _PILLAR_BUILDERS.get(pillar)
    if builder is None:
        return {"pillar": pillar, "status": "blocked", "eligible": False, "criteria": [],
                "blockers": [f"Unknown pillar {pillar!r}."], "next_steps": [], "detail": {}}
    try:
        criteria, detail = builder(row, profile, fit, score)
    except Exception as exc:                       # pragma: no cover - defensive
        return {"pillar": pillar, "status": "unproven", "eligible": False, "criteria": [],
                "blockers": [], "next_steps": [f"Criteria could not be evaluated ({exc})."],
                "detail": {}}

    blockers = [c["note"] or c["label"] for c in criteria
                if c["blocking"] and c["status"] == "unmet"]
    next_steps = [f"{c['label']}: {c['note']}" if c["note"] else c["label"]
                  for c in criteria
                  if c["required"] and c["status"] in ("unmet", "unknown") and not
                  (c["blocking"] and c["status"] == "unmet")]
    status = ("blocked" if blockers else
              "eligible" if not next_steps else "unproven")
    return {"pillar": pillar, "status": status, "eligible": status == "eligible",
            "criteria": criteria, "blockers": blockers, "next_steps": next_steps,
            "detail": detail}


def assess_all_pillars(row: pd.Series, profile: dict, fit: dict, score: dict) -> dict:
    return {p: assess_pillar(p, row, profile, fit, score) for p in PILLARS}


# ====================================================================== Siemens Financial Services

# SFS is a lender and a lessor, not a grant programme, so every line below needs something to
# underwrite. The old check asked whether the startup operated in a capital-intensive SPACE, which
# is a question about its CUSTOMERS, and answered yes for all 18 stored runs — including two pure
# software companies whose only connection to capital equipment was that their users owned some.
SFS_LINES = (
    {"id": "vendor_finance", "label": "Vendor / sales finance",
     "what": "sales-financing programmes so the startup's own customers can finance its equipment",
     "url": SOURCES["sfs_equipment"]},
    {"id": "equipment_finance", "label": "Equipment and technology finance",
     "what": "leasing, rental, usage-based and as-a-service structures for assets the startup needs",
     "url": SOURCES["sfs_equipment"]},
    {"id": "project_finance", "label": "Project and structured finance",
     "what": "debt and equity for energy, mobility and infrastructure projects",
     "url": SOURCES["sfs"]},
    {"id": "corporate_lending", "label": "Corporate lending / growth capital",
     "what": "senior secured debt, revolvers, term loans, asset-based lending and growth capital",
     "url": SOURCES["sfs"]},
)

# Projects SFS finances as projects: an SPV with an offtake, not a product sale.
_PROJECT_TERMS = (r"\bpower (?:plant|purchase)", r"\bppa\b", r"\boff[- ]?take", r"\bepc\b",
                  r"\bconcession\b", r"\bproject financ", r"\bpilot plant\b",
                  r"\bproduction (?:plant|facility|line)\b", r"\brefiner", r"\bgigafactory\b",
                  r"\bcharging network\b", r"\bsolar (?:park|farm)\b", r"\bwind farm\b",
                  r"\bgrid[- ]scale\b", r"\butility[- ]scale\b",
                  r"\brecycling (?:plant|facility)", r"\bcommercial[- ]scale\b",
                  r"\bdemonstration (?:plant|unit)\b", r"\boffshore\b")

# Assets the startup itself would need to acquire and could finance rather than buy outright.
_CAPEX_TERMS = (r"\bproduction line\b", r"\bmanufactur(?:ing)? facility\b", r"\bfleet\b",
                r"\blaboratory\b", r"\bcleanroom\b", r"\breactor\b", r"\bpilot line\b",
                r"\bscale[- ]up (?:plant|facility)\b", r"\bcapital expenditure\b", r"\bcapex\b",
                r"\bchemical (?:process|recycl|upcycl)", r"\bfeedstock\b", r"\bfoundry\b",
                r"\bfab(?:rication)? (?:line|plant)\b", r"\bbioreactor\b", r"\bkiln\b")

# The commercial extraction is what makes an SFS answer possible at all. A run that predates it —
# or one where it never ran — must say "not assessed", never "no". An empty result and a negative
# finding are different facts, and reporting the first as the second is what the employee-history
# status field exists to prevent elsewhere in this codebase.
#
# `funding_stage` is deliberately NOT in this list even though it lives in the same block: it is
# parsed deterministically from a funding string the pipeline already had, so it is present on
# runs where the extraction never ran at all. Treating it as proof of assessment made an offline
# run report a confident "not relevant" about a company nothing had been checked on.
_COMMERCIAL_EVIDENCE_KEYS = ("deployment", "revenue_signal", "certifications", "investors",
                             "sells_hardware", "has_public_api", "pricing_public")


def assess_sfs(row: pd.Series, profile: dict, fit: dict = None) -> dict:
    """Which Siemens Financial Services line, if any, is a real avenue for this startup.

    Returns ``{status, relevant, lines, blockers, rationale, line}`` where status is
    ``relevant`` | ``conditional`` | ``not_relevant`` | ``unassessed``. ``lines`` are ordered
    strongest first and each carries what is still missing, so "conditional" is expressible
    rather than being rounded up to yes.

    The gate that was missing entirely: SFS underwrites credit, so at least one of an asset it can
    take security over, a cash flow it can lend against, or an institutional equity sponsor behind
    the company has to be evidenced. A pre-revenue pure-software company has none of the three and
    is not a financing candidate however industrial its customers are.

    ``unassessed`` is the fourth state and it is load-bearing. This decision rests on the
    commercial posture the profile stage extracts, and a run from before that existed — or one
    whose extraction came back empty — knows nothing either way. Reporting that as "not relevant"
    would hand a reviewer a negative finding the evidence does not support, which is the same
    mistake as reporting an unsearched headcount history as "no history found".
    """
    profile, fit = profile or {}, fit or {}
    row = row if row is not None else pd.Series(dtype=str)
    commercial = _commercial(profile)
    blob = _startup_text(row, profile, fit)
    assessed = bool(commercial) and (
        str(commercial.get("method") or "") == "llm"
        or any(commercial.get(k) for k in _COMMERCIAL_EVIDENCE_KEYS))

    sells_hardware = bool(commercial.get("sells_hardware")) or \
        str(commercial.get("deployment")) == "hardware"
    revenue = str(commercial.get("revenue_signal") or "")
    stage = str(commercial.get("funding_stage") or "")
    institutional = stage in ("series_a", "series_b_plus")
    has_project = _match(blob, _PROJECT_TERMS)
    needs_capex = _match(blob, _CAPEX_TERMS)
    named_customers = [c for c in (profile.get("reference_customers") or []) if str(c).strip()]

    lines, blockers = [], []

    if sells_hardware:
        missing = [] if named_customers else ["named B2B customers to extend financing to"]
        lines.append({"line": "Vendor / sales finance", "id": "vendor_finance",
                      "fit": "strong" if named_customers else "conditional",
                      "rationale": "Sells physical equipment, so its own buyers are the "
                                   "financing counterparty — this is the line that helps the "
                                   "startup close deals rather than fund itself.",
                      "evidence_url": commercial.get("hardware_source", ""),
                      "missing": missing})

    if has_project:
        missing = [] if (revenue in ("contracted", "recurring") or institutional) else \
            ["a contracted offtake or an equity sponsor behind the project"]
        lines.append({"line": "Project and structured finance", "id": "project_finance",
                      "fit": "strong" if not missing else "conditional",
                      "rationale": "Builds or operates plant-scale assets, which SFS finances as "
                                   "projects rather than as a product sale.",
                      "evidence_url": "", "missing": missing})

    if needs_capex or (sells_hardware and revenue):
        missing = [] if (revenue or institutional) else \
            ["revenue or an institutional round to service payments against"]
        lines.append({"line": "Equipment and technology finance", "id": "equipment_finance",
                      "fit": "strong" if not missing else "conditional",
                      "rationale": "Needs capital equipment of its own, which is leasable rather "
                                   "than purchasable outright at this stage.",
                      "evidence_url": "", "missing": missing})

    if institutional and revenue in ("recurring", "contracted"):
        lines.append({"line": "Corporate lending / growth capital", "id": "corporate_lending",
                      "fit": "strong",
                      "rationale": f"Institutional backing ({stage.replace('_', ' ')}) alongside "
                                   f"{revenue} revenue is the profile corporate lending "
                                   "underwrites.",
                      "evidence_url": commercial.get("revenue_source", ""), "missing": []})

    # ---- the financeability gate ------------------------------------------------------------
    if not lines:
        if not assessed:
            # Nothing was looked at, so nothing can be concluded. Say that.
            return {"status": "unassessed", "relevant": False, "lines": [], "blockers": [],
                    "line": "",
                    "rationale": "Commercial posture was not established on this run, so whether "
                                 "SFS has anything to underwrite here is unknown. Re-evaluate to "
                                 "assess it."}
        if not (sells_hardware or has_project or needs_capex):
            blockers.append("No asset, project or equipment is evidenced — SFS finances things it "
                            "can take security over. That the startup's customers are "
                            "capital-intensive is a fact about them, not about this company.")
        if not revenue and not institutional:
            blockers.append("No contracted or recurring revenue and no institutional round "
                            "evidenced, so there is no cash flow to underwrite either.")
        if not blockers:
            blockers.append("Nothing in the evidence maps to an SFS product line.")

    order = {"strong": 0, "conditional": 1}
    lines.sort(key=lambda x: order.get(x["fit"], 2))
    status = ("relevant" if any(x["fit"] == "strong" for x in lines)
              else "conditional" if lines else "not_relevant")
    return {"status": status,
            # Kept a bool for the runs table and the Explore chip, which have always been binary.
            # Only a `strong` line counts: a conditional one is a lead, not a recommendation.
            "relevant": status == "relevant",
            "lines": lines, "blockers": blockers,
            "rationale": lines[0]["rationale"] if lines else blockers[0],
            "line": lines[0]["line"] if lines else ""}
