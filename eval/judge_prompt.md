# LLM-as-judge: machine-written notes

Used only for what code cannot decide (§6.3): whether a note faithfully reflects its extract,
and how useful the note is. Extract correctness (verbatim, page, section, figures) is checked
by code (V1–V5), never by the judge.

You receive one EXTRACT (verbatim document text) and one NOTE (a one-line machine-written
reason why the extract is relevant to an agenda item). The note may be in bokmål, nynorsk or
English.

Return JSON:
- `faithful`: true if everything the note states is supported by the extract; false if the
  note adds facts, numbers or claims that the extract does not contain, or contradicts it.
- `usefulness`: 1 = says nothing beyond "relevant"; 2 = names what the extract covers;
  3 = tells the reader precisely why this passage matters for the item.
- `reason`: at most 20 words.

Known failure modes to watch for in spot checks (20 judged items are checked by hand):
- leniency: judges tend to call vague notes faithful;
- length bias: longer notes get higher usefulness scores;
- weaker judgement on nynorsk text.
