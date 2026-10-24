"""Build the demo caches (backend/data/cache/*.json) from the real, hand-labeled seed posts in seed/*.json.

Seed posts were pulled from X (recent/full-archive search via the X API) and labeled by reading each post.
No API calls are made here; re-run any time:  backend/.venv/bin/python scripts/build_seed.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.analysis import build_document  # noqa: E402
from app.cache import Cache  # noqa: E402

META = {
 "refrigerators": {
  "headline": "Top frustrations with refrigerators: ice makers and water dispensers that keep failing, painful repair and warranty experiences, and compressors that stop cooling.",
  "text": "Of 65 genuine posts (from 164 pulled; ~60% was ads, repair-shop promos and jokes), 58 are negative. Ice makers alone account for 21 posts, often repeat failures followed by $500–800 repairs, and 9 posts push back on smart features, which points to an opening for a simple, reliable, easy-to-repair fridge.",
  "categories": {
   "Ice maker & water dispenser": "Ice makers freezing up, dying, or needing repeat replacement; dispenser clogs and leaks",
   "Repair, warranty & service": "Slow or failed service visits, parts unavailable, warranties not honored, surprise charges",
   "Not cooling / compressor failure": "Units that stop cooling, mostly compressor and control-board failures",
   "Smart features & apps": "Unwanted connectivity, software updates that brick units, 'why does a fridge need a computer'",
   "Durability & longevity": "New fridges dying in 5-6 years vs old ones lasting decades; fragile plastic parts",
   "Leaking": "Water lines freezing and leaking",
   "Price & value": "Premium prices that don't buy reliability",
   "Noise": "Noisy units",
   "other": "Other fridge complaints"},
  "dig": [
   {"label": "Filter to ice maker complaints", "kind": "filter_category", "category": "Ice maker & water dispenser"},
   {"label": "Which brands come up most in repair & warranty?", "kind": "brands", "category": "Repair, warranty & service"},
   {"label": "What do people wish existed?", "kind": "wishes"},
   {"label": "Show the most-liked complaints", "kind": "top_liked"}]},
 "standing desks": {
  "headline": "Top frustrations with standing desks: owners stop standing at them, standing all day hurts their feet and legs, and motors or legs fail and get the desk stuck.",
  "text": "Of 64 genuine posts (from 263 pulled), the two biggest themes are behavioral, not hardware: 15 owners say the desk became 'an expensive shelf' and 15 describe foot, leg or back pain from standing. Another 12 report desks stuck up or down or a leg motor dying, and wobble with monitors and walking pads keeps coming up, so a new entrant could compete on reliability plus built-in habit nudges.",
  "categories": {
   "Bought it, never stand at it": "Desk becomes a shelf; owners forget or never switch to standing",
   "Foot, leg & back pain from standing": "Sore feet, plantar fasciitis, knee and back pain after standing too long",
   "Motor & electronics failures": "Desks stuck up or down, one leg failing, dead motors and control boxes",
   "Assembly & delivery damage": "Day-long assembly, mistakes, cracked or damaged tops on arrival",
   "Wobble & stability": "Monitors shaking at standing height, worse with walking pads",
   "Size, looks & design": "Desks that don't fit the room or look like plain tables; awkward control bars",
   "Warranty & support": "Months-long waits for replacement parts, unresponsive support",
   "Cables & setup": "Cables pulled or things falling when the desk moves",
   "Price & value": "Overpriced tops and frames",
   "other": "Other standing desk complaints"},
  "dig": [
   {"label": "Why do people stop standing?", "kind": "filter_category", "category": "Bought it, never stand at it"},
   {"label": "Filter to motor & electronics failures", "kind": "filter_category", "category": "Motor & electronics failures"},
   {"label": "Which brands come up most in hardware failures?", "kind": "brands", "category": "Motor & electronics failures"},
   {"label": "What do people wish existed?", "kind": "wishes"}]},
 "e-bikes": {
  "headline": "Top frustrations with e-bikes: batteries dying mid-ride, slow or refused repairs, and bikes too heavy to ride or carry without power.",
  "text": "Across 73 genuine posts (from 205 pulled), battery problems dominate once combined: 12 posts about dying mid-ride, 6 about $600–950 replacement packs and 3 about fire risk. Another 10 describe repair waits of weeks to months or shops that won't touch e-bikes, so service and parts availability may matter as much as the bike itself.",
  "categories": {
   "Battery dies mid-ride / range": "Running out of charge mid-ride, leaving a heavy bike with no assist",
   "Repairs, parts & service delays": "Weeks-to-months waits for parts, shops refusing e-bikes, repeat faults",
   "Flats, chains & brakes": "Frequent flats, chains coming off, brakes wearing out or failing",
   "Too heavy to carry or push": "Bikes too heavy for stairs, racks, trains, or pushing home",
   "Cheap build quality": "Budget bikes arriving broken, motors failing just past warranty",
   "Road danger & bike lanes": "Near misses and crashes with cars; bike lanes not built for e-bike speeds",
   "Battery replacement cost": "Replacement packs costing $600-950, sometimes more than the bike",
   "Theft": "E-bikes stolen, often a rider's only way to work",
   "Rules & regulation": "Speed limits, registration laws, fire-risk rules for storage",
   "Battery fire & safety": "Lithium battery fires, especially cheap replacement packs",
   "other": "Other e-bike complaints"},
  "dig": [
   {"label": "Filter to battery complaints", "kind": "filter_category", "category": "Battery dies mid-ride / range"},
   {"label": "Which brands come up most in repairs?", "kind": "brands", "category": "Repairs, parts & service delays"},
   {"label": "What do people wish existed?", "kind": "wishes"},
   {"label": "Show the most-liked complaints", "kind": "top_liked"}]},
}


# Unmet needs stated or clearly implied by specific posts (written from each post's text).
WISHES = {
 "2109671043572850731": "A dumb, cheap, reliable fridge",
 "2109907714482811297": "A fridge that shuts down safely and alerts you when it gets warm",
 "2113300962723205521": "A smart fridge with a screen and an inside camera",
 "2111928447111205284": "A long-lasting fridge without wi-fi or an ice maker",
 "2112198321083134122": "Simple top-freezer models without ice makers",
 "2105634585732137214": "A fridge without a fragile built-in ice maker",
 "2111555701772591444": "An ice maker as dependable as an old ice tray",
 "2109730390600560930": "A fridge without a computer in it",
 "2105433490649161755": "Repairs that cost less than a new fridge",
 "2107962207929577951": "Replacement parts in days, not 8+ weeks",
 "2112780076869877902": "A desk that keeps monitors still, even with a walking pad",
 "2093411857273139621": "A desk stable enough to use while walking",
 "2035767020721930312": "A setup that lets them move instead of standing still",
 "2101497572305059842": "A standing desk with drawers that looks like a real desk",
 "2054913557095916006": "A standing desk that fits the home's look",
 "2106082485079523463": "Controls placed so they don't hit your knees",
 "2113623807244013868": "A portable standing desk that actually gets tall enough",
 "2102473807655059594": "A nudge to actually raise the desk",
 "2102805978718621908": "Built-in comfort for feet when standing",
 "2107695149124030495": "Cable management that moves with the desk",
 "2049008937211445265": "Replacement parts without 5-month waits",
 "2109323420727140728": "An e-bike that isn't a heavy brick when the battery dies",
 "2113422694209519696": "A lighter e-bike",
 "2086526265973239964": "A lighter model that still feels sturdy",
 "2102632773953736880": "An easy way to get a heavy e-bike up stairs",
 "2055002788321763770": "Local shops that can repair e-bike electrics",
 "2111834688151031867": "Mobile repair for e-bikes bought online",
 "2093847433738649914": "Affordable replacement batteries",
 "2045521913699500237": "Safe, certified batteries at a fair price",
 "2103223900306076023": "Brakes that can actually stop the bike",
 "2110832633211170935": "Bike lanes designed for e-bike speeds",
 "2104393453945913502": "Secure charging spots in apartment buildings",
}


def main():
    cache = Cache(ROOT / "backend" / "data" / "cache")
    for f in sorted((ROOT / "seed").glob("*.json")):
        seed = json.loads(f.read_text())
        topic, meta = seed["topic"], META[seed["topic"]]
        posts = []
        for p in seed["posts"]:
            p = dict(p)
            p["rep_llm"] = {1: 0.35, 2: 0.6, 3: 0.9}[p.pop("r", 2)]
            p["wish"] = WISHES.get(p["id"], "")
            posts.append(p)
        from app.analysis import finalize_representativeness
        finalize_representativeness(posts)
        stats = {"raw": seed["raw_fetched"], "deduped": seed["deduped"],
                 "noise_dropped": seed["deduped"] - len(posts), "search_calls": seed["search_calls"],
                 "noise_reasons": {"ads, deals, brand/repair promos, jokes, off-topic (manual review)": seed["deduped"] - len(posts)}}
        v = seed.get("volume")
        volume = {"query": v["query"], "granularity": "day", "label": "All posts mentioning the topic, last 7 days",
                  "series": [{"date": d, "count": c} for d, c in v["data"]]} if v else None
        doc = build_document(topic, posts, meta["categories"], {"headline": meta["headline"], "text": meta["text"]},
                             meta["dig"], stats, source="seed:x-api-search+manual-labels",
                             model={"label": "manual (seed)"}, volume=volume,
                             notes=["Seed data: real X posts, labeled by hand; brand counts reflect search terms, not market share."],
                             generated_at="2026-10-24T19:30:00+00:00")
        cache.put(topic, doc)
        print(f"{topic}: {len(posts)} posts, top: {[c['name'] + ' ' + str(c['count']) for c in doc['categories'][:3]]}")


if __name__ == "__main__":
    main()
