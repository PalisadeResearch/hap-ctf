#align(center)[
  #text(17pt, [A Typst Demo Document])

  #grid(columns: (1fr,) * 1, row-gutter: 24pt)[
    Your name #footnote[Correspondence to #link("mailto:example@palisaderesearch.org")]
  ]

  #datetime.today().display()
]

#set heading(numbering: "1.")

= Introduction

This is a demonstration document created with Typst that includes a figure.

#figure(
  image("hello.svg", width: 80%),
  caption: "A sample figure",
) <hello>

Here we can reference @hello in the text.
