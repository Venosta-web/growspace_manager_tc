# Growspace Manager TC — Domain Glossary

Tissue-culture companion to Growspace Manager: preserving phenotypes in vitro
and tracking the work of keeping them alive. This context references
phenotypes; it never owns them.

## Lines & Cultures

**Culture Line**
A preserved in-vitro lineage of one phenotype, started by a single Introduction. It owns the Phenotype Reference, the per-Culture-Stage replate intervals, and the medium preference expressed through Pairings.
_Avoid_: strain entry, culture (alone), phenotype copy

**Culture**
One continuously maintained plantlet group occupying a single vessel. Its identity survives a Replate into a fresh vessel and ends at Discard or Graduation; dividing it creates new Cultures. The unit every Maintenance Action acts on.
_Avoid_: vessel, jar, plant, specimen

**Culture Stage**
Whether a Culture is in `multiplication` or `rooting`. The stage selects which replate interval from the Culture Line applies.
_Avoid_: phase, media stage

**Plantlet Count**
The number of plantlets in a Culture, recorded at each Replate. Optional but load-bearing: per-vessel multiplication rate is only derivable later if the count exists now.
_Avoid_: vessel size, density

**Location**
A free-text optional label for where a Culture's vessel physically sits (shelf, rack, tub). Filterable text, never a structured hierarchy.
_Avoid_: zone, growspace, shelf list

**Introduction**
The act of starting a Culture Line by placing an explant from a phenotype into culture. One line, one introduction.
_Avoid_: import, inoculation

## Maintenance

**Maintenance Action**
One recorded act on a Culture from the fixed vocabulary: Replate, Discard, note, stage move to rooting, or Graduation. The closed set is what keeps history computable.
_Avoid_: activity, log entry

**Replate**
Transferring a Culture onto fresh Culture Medium, optionally dividing it into several new Cultures in the same act. Resets the Culture's Replate Due Date.
_Avoid_: subculture, transfer, refresh

**Replate Due Date**
The day a Culture needs its next Replate: its last Replate plus the interval its Culture Line defines for its current Culture Stage. Past that date without a Replate, the Culture is overdue.
_Avoid_: schedule date, next task

**Discard**
Ending a Culture with a reason (contamination, spent, mistake). A discarded Culture stays in history; it is not deleted.
_Avoid_: delete, remove

**Graduation**
Taking a Culture out of vitro to acclimatize. It ends the Culture and may create the corresponding Plant in Growspace Manager through its public service.
_Avoid_: harvest, ex vitro transfer

## Medium & Pairings

**Culture Medium**
A named, versioned formulation — base salts, additive and hormone entries with concentrations, agar, sugar, pH — that Cultures grow on. "Media" unqualified is reserved in Growspace Manager for substrate and is never used for Culture Medium.
_Avoid_: media, media recipe, substrate, feed

**Medium Version**
An immutable snapshot of a Culture Medium's formulation. Every Plating pins one; editing a medium creates a new version rather than rewriting history.
_Avoid_: recipe edit, draft

**Plating**
One placement of a Culture onto a specific Medium Version — at Introduction and at every Replate. The evidence trail behind Pairings.
_Avoid_: pour, fill

**Pairing**
A curated record endorsing one phenotype on one Culture Medium. "Which phenotypes suit this medium" and "which media suit this phenotype" are both views of the pairing set, not separate data.
_Avoid_: recommendation (Growspace Manager's strain-library sense), rating, match

## References

**Phenotype Reference**
An opaque phenotype ID owned by Growspace Manager's strain library, stored with a display-name snapshot. It is never a copy of the phenotype record.
_Avoid_: phenotype copy, local strain, lookup

**Missing Phenotype**
The explicit state of a Phenotype Reference whose ID no longer resolves in Growspace Manager. Shown from the name snapshot; re-linkable or archivable, never silently dropped.
_Avoid_: orphan, broken link
