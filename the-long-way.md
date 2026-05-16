# The Long Way

*A field guide for the next three years.*

---

## Why this exists

This is a syllabus for going from "I can do my job but I don't really understand what's underneath" to "I can build the thing I want to build, and I understand the layers below it." The author is a filmmaker by primary identity, a DevOps engineer by trade, and a founder building a preproduction platform. The technical depth here is in service of being able to contribute substantively to a product he is bootstrapping into a business — not in service of becoming a great engineer for its own sake.

The plan is roughly three years at ~10 hours/week. It is deliberately not optimized for the shortest path to a job; it is optimized for actually understanding things. Two pieces of writing shape the philosophy:

- [Lane Wagner — Learn to Code the Slow Way](https://www.boot.dev/blog/education/learn-to-code-the-slow-way/) — stop hunting shortcuts; the shortest path is to actually get good.
- [Austin Henley — Challenging projects every programmer should try](https://austinhenley.com/blog/challengingprojects.html) — the way to truly understand a system is to build a small version of it.

---

## Guiding principles

**Build the thing under the thing.** When learning Docker, also build a tiny container runtime. When learning HTTP, also write a server from raw TCP. When learning Kubernetes, also write a tiny scheduler. The depth comes from the building, not the reading.

**Think in layers.** Every system on your computer is a stack of layers, each delegating to the one below. When something behaves unexpectedly, the question is never "why doesn't this work" — it is always "which layer is doing something I don't expect." This is the meta-skill that makes every other skill in this plan compound. Cultivate it deliberately: when you use a tool, ask what layer it sits on; when you debug, ask which layer the symptom appeared at and which layer it actually originated from.

**Lineage, not regress.** When a tool you use intrigues you, occasionally trace it back to *one* direct ancestor — the framework it was inspired by, the paper it implements, the older tool it replaced — so you can read the present-day thing with new eyes. This is *Sorcerer → Wages of Fear*: you don't go all the way back to silent cinema, you go back one step. Features stop feeling arbitrary and start feeling motivated when you've seen the pain they were invented to solve. The trap to avoid is believing you must learn every ancestor before you can understand the descendant — that you can't really understand React until you learn Elm, can't understand Elm until you learn Haskell, can't understand Haskell until you learn lambda calculus. The chain is infinite. The lesson is at the first step. **The deliverable of any lineage detour is a one-page contrast — what the descendant kept, dropped, added, and why — written when you return to the present-day tool. If you can't write that note, the detour was tourism.** The syllabus below names the specific lineage detours that are worth the time; do those, and resist the rest.

**Slow is fast.** Three years feels long. It isn't. Most engineers spend ten years not learning this stuff.

**One thing at a time, deeply.** Two books in parallel maximum. One main project at a time.

**Boring consistency beats heroic sprints.** Ninety minutes a day six days a week, for three years, beats eight hours on Saturday and nothing the rest of the week. Sundays off entirely — rest is part of the protocol, not a failure of it.

**Write to know you know.** If you can't explain it in a blog post or a notebook page, you don't know it yet.

---

## The daily and weekly rituals

**Daily, every day except Sunday:**

- **Morning, 30 min — Reading.** Paper book, paper notebook, no laptop. Same chair, same time. This is sacred.
- **Anki review, 10–15 min.** Whenever — commute, lunch, before bed. Add 3–5 new cards per day from what you read and built. No more.
- **Evening, 60–90 min — Hands-on.** boot.dev, the side build, or the main project. In nvim. Without AI writing code for you (using AI to *explain* concepts is fine and good — just not to autocomplete logic).

**Weekly:**

- **Saturday, 3–4 hour deep block** — bigger project work, or a chapter that needs uninterrupted thought.
- **Sunday — off.** Genuinely off. Walk, read fiction, make a film, see people.
- **Friday evening, 20 min — review.** What did I learn this week? What's still fuzzy? Update the tracker.

**Monthly:**

- One blog post or detailed notes document about something you learned that month.
- End-of-month review — what worked, what didn't. The plan is allowed to evolve, but only at month boundaries, not in the middle of a tough week.

---

## The standards

These are the constraints that shape *how* you learn, not just *what*.

- **Anki daily**, no exceptions. Cards for definitions, mental models, syscalls, Go idioms, bash one-liners.
- **Code in [nvim](https://neovim.io/).** Start minimal — built-in LSP, [telescope](https://github.com/nvim-telescope/telescope.nvim), a [tree-sitter](https://github.com/nvim-treesitter/nvim-treesitter) setup, nothing more. Resist the urge to spend a week on dotfiles.
- **No AI-generated code in main work.** AI for explanation, fine. AI writing your functions, no.
- **Hand-write notes from books.** Pen and paper. Typing is too easy and you don't compress.
- **Raspberry Pi as your home Linux lab.** Headless, ssh-only. Best Linux teacher money can buy.
- **Everything in git, public.** Notes, projects, dotfiles. For accountability and for future-you.
- **Physical journal, weekly entries.** What you struggled with, what clicked.

---

## The retrieval loop

Before the practices themselves, the most important idea: **all of these compound only if you retrieve, not just encode.** This is the principle underneath spaced repetition, and it applies to everything in the syllabus — not just Anki cards.

Most engineers' learning fails the same way. They read a book, feel like they understood it, and never test themselves. Three months later the chapters are gone. They contribute to a project, never look at the PR again, and the understanding evaporates. They build a side project, push it to GitHub, and a year later can't explain how it worked.

The fix is a simple loop, run forever:

**Capture → Retrieve → Connect → Test.**

- **Capture** is the encoding step. Notes by hand, Anki cards, blog drafts, code commits. This is what most people already do.
- **Retrieve** is what you're missing. Pulling the knowledge *out* of your head, at spaced intervals, without looking at the source. This is where memory consolidates.
- **Connect** is what makes islands into a continent. Each new thing you learn should be linked, in your notes, to two or three things you already know. "This is like X, except…" is the most powerful sentence in learning. Lineage detours are a deliberate version of this same move — connecting the descendant to its ancestor.
- **Test** is the final form of retrieval — applying the knowledge in a new context. Explaining it to someone. Predicting how a system would behave. Building something with it. If you can do this, you actually know it.

### Anki, the foundation

[Anki](https://apps.ankiweb.net/) is the single tool every engineer should use and almost none do. It is a free, open-source flashcard app that schedules reviews using a spaced-repetition algorithm — cards you remember easily move to long intervals (months, then years); cards you forget come back tomorrow. Used consistently, it makes forgetting almost impossible.

**The practice:** 10–15 minutes daily, anywhere. Add 3–5 new cards a day, no more — the deck stays sustainable. Review whatever Anki gives you. Never rate a card "easy" lazily; be honest about whether you actually retrieved it.

**What goes on cards:**
- Definitions you keep forgetting (what's the difference between a process and a thread? What's a virtual address?)
- Syntax you reach for often but type slowly (Go's `select` statement, common bash patterns, SQL window functions)
- Mental models, phrased as questions ("what happens when you type a URL into a browser?")
- **Layer maps** — for each major system you use (DNS resolution, HTTP request lifecycle, package install, git push, ssh login, boot, container start, TLS handshake), maintain a card that lists every layer the request passes through, in order. These are the highest-leverage cards you'll have when debugging. Today's bug is almost always at a layer you forgot existed.
- **Diagnostic tools, indexed by layer** — when something is wrong at layer X, what tool do I reach for? Cards like "to inspect DNS resolution at the OS level on macOS, what tool?" → `dscacheutil -q host -a name <hostname>`. Build this index over time so the right tool appears in your hand without searching.
- **Lineage contrasts** — when you finish a lineage detour, the one-page note compresses into 1–2 cards. "What did Kubernetes inherit from Borg, and what did it deliberately change?" "What does the relational model assume that NoSQL gives up?" These cards are durable because they encode *why* features exist.
- Numbers worth memorizing ([latency numbers every programmer should know](https://gist.github.com/jboner/2841832))
- Code idioms — *not* whole programs, but small recognizable patterns

**What does *not* go on cards:**
- Anything you can look up in 5 seconds (don't memorize the standard library)
- Long passages from books (compress them into a question first)
- Things you don't understand yet — Anki is for retention, not learning. Understand first, then add the card.

**Resources:**
- [Augmenting Long-term Memory](http://augmentingcognition.com/ltm.html) — Michael Nielsen's essay; the canonical "why Anki" piece. Read this before you start.
- [How to remember everything you learn — Andy Matuschak](https://andymatuschak.org/books/) — the modern theory of spaced repetition.
- [Twenty rules of formulating knowledge](https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge) — Piotr Wozniak (the inventor of SRS) on how to write good cards. Read this once a year.
- [Janki Method](https://www.jackkinsella.ie/articles/janki-method) — applying Anki to programming specifically.

### The review schedule

Anki handles itself. The other practices need explicit retrieval rituals scheduled into your week, month, and quarter. These are non-negotiable in the same way the morning reading is.

**Friday evening — Weekly review *(20 min)*.** Open last week's notes (book, code-reading, debugging). Without looking at them, write down the three most important things you learned. *Then* compare to your notes. The gap between what you remembered and what you wrote is the diagnostic — that's what your Anki cards for next week should target. Update the tracker.

**Last Saturday of the month — Monthly retrieval *(60 min)*.** Pull up the last four weeks of code-reading notes. Re-read your own one-page summaries. For each codebase, ask yourself: could I sketch its architecture from memory right now? If not, that codebase needs revisiting before any new ones. Same exercise for the month's PRs (read your diffs and the reviewer's comments) and for any blog posts (re-read your own posts looking for things you'd now disagree with).

**End of quarter — Quarterly synthesis *(2–3 hrs).** Re-read three months of journal entries. Re-read three months of monthly retrospectives. Write a single page: what changed about how you think? What can you now do that you couldn't 90 days ago? What's still confusing? This page goes in the journal and is the most valuable single artifact you produce that quarter.

**End of year — Annual review *(half a day).** Re-read all four quarterly syntheses. Re-read your year's blog posts. Look at your GitHub contribution graph. Write the year-in-review document that captures the trajectory. This is also when you reconsider the plan — the syllabus is allowed to evolve at year boundaries far more than at month boundaries.

The principle: **the further out the review, the higher-leverage it is.** The Friday review catches what's already slipping. The annual review tells you who you've become.

---

## Active practices

The reading list teaches you what good code looks like. These practices teach you to *see* it. Each practice has two parts — a *do* (the encoding) and a *retrieve* (the consolidation). Most engineers do only the first half and wonder why their understanding doesn't compound. Don't be one of them.

### Read real code, weekly

Most of what you'll write professionally will be modifying existing code, not greenfield projects. You need to be fluent at *reading* code, not just writing it. Pick one piece of real code per week and study it for an hour.

**The practice:** Saturday morning, hour one. Pick a target, read it, write a one-page summary in your notebook of what you learned, what was confusing, what was beautiful. Add 1–2 Anki cards. Push the notes to your public repo.

**Picker:** [repopick](https://sauravsuresh.github.io/long-way-engine/repopick/) materializes this practice — one curated repo at a time from a 41-entry seed, scoped to a specific entry point with a concrete reading question. Mark the week's read complete to unlock the next pick; progress is per-browser in localStorage.

**What to read, in roughly increasing difficulty:**
- **Go standard library** — start with simple packages: [`strings`](https://pkg.go.dev/strings), [`sort`](https://pkg.go.dev/sort), [`io`](https://pkg.go.dev/io). Then [`net/http`](https://pkg.go.dev/net/http), [`encoding/json`](https://pkg.go.dev/encoding/json). The stdlib is famously well-written and is your single best teacher for Go idiom.
- **Small canonical Go projects** — [BoltDB](https://github.com/etcd-io/bbolt) (a single-file embedded KV store, ~6k lines), [groupcache](https://github.com/golang/groupcache), [hashicorp/raft](https://github.com/hashicorp/raft).
- **Tools you use daily** — [git](https://github.com/git/git) (in C), [tmux](https://github.com/tmux/tmux), [bat](https://github.com/sharkdp/bat), [fzf](https://github.com/junegunn/fzf), [ripgrep](https://github.com/BurntSushi/ripgrep). Even reading the README and design docs of these is enlightening.
- **Pieces of larger systems** — once comfortable, dip into [Kubernetes](https://github.com/kubernetes/kubernetes/tree/master/pkg/scheduler) (kube-scheduler is the most accessible component), [SQLite source](https://www.sqlite.org/src/doc/trunk/README.md), [Redis](https://github.com/redis/redis) (clean C, well-commented).

**How to read code without drowning:**
1. Read the README and any `ARCHITECTURE.md` first. If there isn't one, that's a signal about the project.
2. Run the tests. Look at what they test — that tells you what the maintainers think is important.
3. Find the entry point (`main.go`, the function the binary calls). Trace one path through the code, ignoring everything else.
4. Pick one feature you understand from the outside and read how it's implemented.
5. Don't read top-to-bottom. Code is a graph, not a book.

**Retrieval:**
- *That same day:* before going to bed, close the notebook and write down (on a separate page) the three design choices that surprised you. Then check.
- *One week later:* during Friday review, sketch the codebase's architecture from memory in 10 minutes. Compare to your notes. The gaps tell you what to add as Anki cards.
- *One month later:* during monthly retrieval, pick a *new* problem and ask "would BoltDB's approach work here? Why or why not?" If you can answer, you understood it. If not, re-read your notes — don't re-read the code yet.
- *Three months later:* in your quarterly synthesis, pick one codebase from the quarter and write a short post comparing its design to another. This is the highest form of retrieval — applying the knowledge by *contrasting* it.

**Resources:**
- [Mitchell Hashimoto — Advanced Testing in Go](https://www.youtube.com/watch?v=8hQG7QlcLBk) — the patterns, mostly stolen from real codebases.
- [Read the source, Luke](https://www.troyhunt.com/the-greatest-developer-skill-of/) — Troy Hunt on the underrated skill.
- [Litmus's "How to read source code"](https://lethain.com/reading-source-code/) — Will Larson's take.

### Trace one thing, weekly

This is the practice that builds the meta-skill of layered thinking. Every system you use — `git push`, `apt install`, opening a webpage, ssh'ing into the Pi, your container starting up — is a stack of layers passing the request down and the response back up. Most engineers operate on the top layer for a decade and never look beneath. The way to stop being that engineer is to deliberately, weekly, look beneath.

**The practice:** 30–60 minutes, Sunday evening or whenever fits. Pick a single thing your computer "just does." *Observe* it doing that thing using real tools — `strace`, `tcpdump`, `dtrace`/`dtruss` on macOS, `dig +trace`, browser devtools network tab, `lsof`, `ss`, `ps`, the file `/proc/<pid>/`. Don't read about it abstractly; watch it happen. Write a layer-by-layer trace in your notebook: at each layer, what crosses the boundary? what tool can observe it?

**Targets, in roughly increasing order of difficulty:**

*Phase 1, weeks 1–8:*
- What happens when I type a URL into a browser? (Do this in week 1. The [canonical exercise](https://github.com/alex/what-happens-when).)
- What does `ls` actually do? (Use `strace ls`.)
- What happens when I press Enter in bash? (Trace from keystroke → terminal → shell → fork → exec → exit code.)
- What happens when I `ping google.com`? (DNS, then ICMP. Watch with `tcpdump`.)

*Phase 1, weeks 9–24, after the networking book:*
- What happens when I `ssh pi`? (DNS, TCP, key exchange, channel multiplexing. Use `ssh -vvv` and `tcpdump`.)
- What happens when I `git push`? (SSH or HTTPS, pack negotiation, ref update.)
- What happens when I `curl https://example.com`? (DNS, TCP, TLS handshake, HTTP. Use `curl -v` and Wireshark.)
- What happens when I open `gitea.mydomain.com` in a browser? (Trace your own Pi setup — DNS, your router, the Pi, ufw, nginx, gitea.)
- What happens when a Let's Encrypt cert renews? (ACME protocol, DNS challenge or HTTP challenge, certificate chain.)

*Phase 2 onward, as the knowledge deepens:*
- What happens when I `docker run`? (Image pull, namespace creation, cgroup setup, OCI runtime.)
- What happens when I `kubectl apply`? (kubectl → apiserver → etcd → controller → scheduler → kubelet → container runtime.)
- What happens when Postgres serves a query? (Use `EXPLAIN`, `pg_stat_statements`, log statements, watch the query plan.)
- What happens when a goroutine blocks on a channel? (Read the runtime source.)

**The rule:** you are not allowed to use the abstract phrase "and then it does X." Either you can name a tool that lets you observe it doing X, or you don't actually know.

**Retrieval:**
- *That same evening:* convert the layer-by-layer trace into one Anki card titled "[X] resolution layers" — each layer in order, with the tool that observes it. This card type is the most valuable kind you'll make.
- *Six months later:* re-trace the same target. Compare to the original. What do you understand now that you didn't? Things you observed correctly without notes are now real knowledge. Things you got wrong before but right now are growth, made visible.
- *Annually:* read your full collection of traces. The pattern of *what kinds of layers you missed* tells you where your mental model has blind spots — and is the single best input to next year's Anki priorities.

**Resources:**
- [What happens when you type google.com into your browser](https://github.com/alex/what-happens-when) — the canonical example. Do this one in week 1.
- [Julia Evans — Bite Size Linux, Bite Size Networking, How DNS Works, How Containers Work](https://wizardzines.com/) — every zine in this series is a tracing exercise compressed into 30 pages. Buy them all.
- [Brendan Gregg — Linux Performance Tools tour](https://www.brendangregg.com/linuxperf.html) — the map of every tool that observes a layer of the Linux kernel.
- [strace — How to use it](https://jvns.ca/blog/2014/05/12/an-introduction-to-strace/) — Julia Evans' intro.
- [tcpdump tutorial](https://danielmiessler.com/study/tcpdump/)
- [bpftrace one-liners](https://github.com/iovisor/bpftrace/blob/master/docs/tutorial_one_liners.md) — once you're past Phase 1, this is the modern observability frontier.

### Contribute to open source, monthly

Reading is half the practice. The other half is making changes — even tiny ones — to code you didn't write. This is where you learn to navigate unfamiliar codebases, write tests for code you barely understand, and submit work for public review. Aim for one PR per month, of any size.

**The practice:** Once a month, find a small bug or doc improvement in a project you use. Open a PR. Even a typo fix in a README is a valid first PR — it teaches you the contribution flow without high stakes. Build up to small bug fixes, then real features. By month 18 you should be capable of contributing meaningful patches to projects in Go.

**Where to find good first issues:**
- [`good-first-issue` on GitHub](https://github.com/topics/good-first-issue) — projects that explicitly tag beginner-friendly work.
- [up-for-grabs.net](https://up-for-grabs.net/) — curated list of welcoming projects.
- [CodeTriage](https://www.codetriage.com/) — sends you one open issue per day from a project you choose.
- The boot.dev community itself — projects from your peers often have low-stakes contribution opportunities.

**A philosophy:**
- Your first 5 PRs should be tiny: typo fixes, doc improvements, dependency updates. The point is to learn the *process* (forking, branching, PR conventions, code review), not to write hard code.
- Read three recently-merged PRs in a project before opening your own. The conventions live there.
- Engage with criticism graciously. Public code review is a skill, both giving and receiving.

**Retrieval:**
- *Right after the PR merges or closes:* write a paragraph in your journal — what was the bug, what was the fix, why was the maintainer's review feedback correct (or not)?
- *Each Friday review:* if you opened a PR this week, re-read it once. Read the diff like a stranger would. What's clear? What isn't?
- *Quarterly:* pull up your last 3 months of PRs and re-read them as a set. You'll see your own patterns — what kinds of bugs you keep introducing, what kinds of code you tend to write. That's the meta-skill.

**Resources:**
- [How to contribute to open source — opensource.guide](https://opensource.guide/how-to-contribute/) — GitHub's official primer.
- [First Contributions](https://github.com/firstcontributions/first-contributions) — a hands-on tutorial repo for your literal first PR.
- [Julia Evans — How to ask good questions](https://jvns.ca/blog/good-questions/) — required reading before you ever post in an OSS issue thread.

### Build the thing under the thing, quarterly

This is the Henley principle, formalized as a recurring habit. Once a quarter, pick a tool or system you use and build a tiny version of it from scratch. The optional branches in the syllabus (text editor, toy HTTP server, toy container runtime, toy scheduler, KV store, Raft) are all instances of this practice.

**The practice:** Pick a small target. Time-box: 20–60 hours over 4–8 weeks. The goal is not to build something useful — it's to demystify a category of software. When you're done, write a blog post about what surprised you.

**Beyond the optional branches in the syllabus, ideas worth pursuing:**
- A toy DNS resolver (after Phase 1 networking) — *especially valuable*: builds the exact mental model that prevents the "why isn't my hosts file blocking this" class of problem
- A toy git (`init`, `add`, `commit` — surprisingly tractable; see [Building Git](https://shop.jcoglan.com/building-git/) by James Coglan)
- A toy load balancer
- A toy ray tracer (one weekend with Peter Shirley's [Ray Tracing in One Weekend](https://raytracing.github.io/))
- A toy regex engine (see [Russ Cox's series](https://swtch.com/~rsc/regexp/))
- A toy SQL query engine (after DDIA)
- An emulator for a simple system (CHIP-8 is canonical)

**Retrieval:**
- *During the build:* commit daily, with messages that explain *why*, not what. Months later you will read these and they'll be your retrieval prompts.
- *On finishing:* write the blog post immediately, before the details fade. The act of explaining is itself the deepest retrieval.
- *Six months later:* try to extend the project with a feature you didn't originally plan. If you can do it without re-reading your own code, the understanding stuck. If not, that's data — your future projects need better internal documentation.
- *Each year:* in your annual review, list the projects you built that year. For each, write a single sentence that captures the *one big idea* you internalized. If you can't, the project didn't compound.

**Resources:**
- [Build Your Own X](https://github.com/codecrafters-io/build-your-own-x) — exhaustive list, sorted by category. Bookmark.
- [Austin Henley — Challenging projects every programmer should try](https://austinhenley.com/blog/challengingprojects.html) and the [sequel](https://austinhenley.com/blog/morechallengingprojects.html).
- [Codecrafters](https://codecrafters.io/) — paid but excellent: structured "build your own X" challenges with automated testing.

### Lineage detours, opportunistic

The lineage practice is *not* a recurring schedule like the others. It is opportunistic — triggered when the syllabus reaches a topic that has a flagged lineage detour (see the syllabus modules below), or rarely, when you encounter a tool in your work that genuinely fascinates you and a one-step ancestor would clarify it.

The syllabus has specific lineage detours embedded inside individual modules — RFC 1945 before deepening into modern HTTP, Codd's paper before going deep on Postgres, the Borg paper before Kubernetes, and a few others. Each is short (5–15 hours), sized to a weekend, and chosen because the ancestor genuinely sharpens the descendant. Do those when you reach them. Resist the urge to add more.

**The discipline that keeps this from devouring the plan:**

- **Time-box hard.** 5–15 hours total per detour. A weekend or two. Not a month. Not "I'm now learning Haskell for real."
- **Go back one step, not all the way.** When you study Codd's relational model to understand Postgres, you do not then go study set theory to understand Codd. The chain is infinite; the lesson is at the first step.
- **The deliverable is a contrast, not a competence.** Output a one-page note (or short blog post) of the form "[ancestor] does X this way; [descendant] does it that way; the descendant kept Y, dropped Z, added W; here's why." If you can't write that note, you haven't extracted the lesson yet — and the detour was tourism.
- **Triggered by curiosity, not by anxiety.** "I love X — where did it come from?" is the practice. "I can't really understand X until I learn Y" is the trap. The first sentiment leads back to the present-day tool with new eyes; the second pulls you into an infinite regress where you never build anything.

**Retrieval:**
- *Right after the detour:* write the contrast note. Non-negotiable. Compress it into 1–2 Anki cards within a week.
- *Three months later:* re-read the contrast note while working with the descendant tool. Are the features you previously took for granted now visible as design choices?
- *Annually:* re-read all the year's contrast notes together. Pattern-match across them — what kinds of features tend to survive from ancestor to descendant? What kinds tend to get dropped? This meta-pattern is the deepest lesson and is invisible without the longitudinal view.

**Resources:**
- [Papers We Love](https://paperswelove.org/) — a community organized exactly around this practice. The repo and meetup talks are a curated lineage map for computer science.
- [The Morning Paper (Adrian Colyer's archive)](https://blog.acolyer.org/) — a working engineer's project of reading one foundational paper per day for years. The summaries are a cheat code for finding the right ancestors quickly when one isn't already named in the syllabus.
- [Hillel Wayne's writing](https://www.hillelwayne.com/) — exemplary contrast-note style; read a few of his posts to see what good lineage writing looks like.

### Operate your own infrastructure, continuously

Hosting your own services on the Pi is not a one-time setup — it's an ongoing practice. You learn how things really break by running them.

**The practice:** Treat the Pi homelab as a real production environment. Each month, do at least one of:
- Add a service you use to it (RSS reader, bookmark manager, photo backup, whatever).
- Set up monitoring or alerting for an existing service.
- Break something deliberately, document the failure, write the postmortem.
- Migrate a service from one tool to another (e.g., switch from cron to systemd timers, or from one reverse proxy to another).
- Audit and tighten security — review ufw rules, rotate keys, check for unattended-upgrades misconfigurations.

**Self-hostable services worth running:**
- [gitea](https://about.gitea.com/) (Phase 1)
- [Miniflux](https://miniflux.app/) for RSS
- [Linkding](https://github.com/sissbruecker/linkding) for bookmarks
- [Vaultwarden](https://github.com/dani-garcia/vaultwarden) for password management
- [Immich](https://immich.app/) for photo backup
- [Plausible](https://plausible.io/self-hosted) for your blog's analytics

**Retrieval:**
- *Keep a postmortem log.* Every time something on the Pi breaks — even small things — write a 5-line entry: what failed, what you thought first, what was actually wrong, what you'll do differently. This is the most valuable notebook you'll keep over three years.
- *Monthly:* re-read last month's postmortems before doing the next month's work. The same kind of failure shouldn't surprise you twice.
- *Quarterly:* take a service you set up 90+ days ago and try to explain its full configuration from memory — DNS, certs, reverse proxy, firewall rules, backup. The gaps are where you operated on autopilot.

**Resources:**
- [r/selfhosted](https://www.reddit.com/r/selfhosted/) — the homelab community, useful for ideas and warnings.
- [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) — exhaustive list.
- [Brendan Gregg — Linux Performance](https://www.brendangregg.com/linuxperf.html) — when something is slow, this is the map.

### Write to know you know, monthly

A blog post is the highest form of compression you can apply to a thing you learned. If you can't explain it to a stranger in writing, you don't know it.

**The practice:** One published post per month, minimum. 800–2000 words. Topics drawn from what you learned that month. Public, your real name, your domain.

**What to write about:**
- Something you struggled with and how it finally clicked. (These are the most valuable posts on the internet.)
- A walkthrough of something you built — design decisions, what failed, what worked.
- Notes on a paper or book chapter, in your own words.
- A small tool or script you wrote, with the problem it solves.
- **A "trace" post** — pick one of your weekly traces and write it up as a public layer-by-layer explanation. These age well; they become reference material for future-you and for strangers Googling at 2am.
- **A "lineage" post** — a contrast note from a lineage detour, expanded for a public audience. "What Kubernetes inherited from Borg, and what it deliberately changed." These posts are rare on the internet and disproportionately valuable.

**Standards for the writing:**
- Don't wait until you're an expert. Beginners explaining what they just learned are uniquely valuable — experts have forgotten what was hard.
- Show your work. Code samples, diagrams, real numbers from your experiments.
- Link to your sources. Be the kind of writer who pays the citation tax.
- Don't optimize for going viral. Optimize for being useful in five years.

**Retrieval:**
- *Six months after publishing:* re-read your post. Note where you'd disagree with past-you, where you'd add nuance, where you got something wrong. That gap is your growth, made visible.
- *Annually:* re-read every post you wrote that year. Pick the three you're most proud of and the three that aged worst. The patterns will surprise you.
- *Whenever someone asks a question you've already written about:* link them to your post and re-read it yourself. You'll find things to update.

**Resources:**
- [Julia Evans — How I write blog posts](https://jvns.ca/blog/2016/05/22/how-i-write-blog-posts/) — practical, low-bar.
- [Patrick McKenzie — How to write technical content](https://training.kalzumeus.com/newsletters/archive/advice_on_writing) — career-altering writing advice.
- [Gwern — On writing](https://gwern.net/about) — extreme version of taking writing seriously.
- Hosting: [Astro](https://astro.build/), [Hugo](https://gohugo.io/), or just plain HTML on your Pi.

### Debug deliberately, weekly

Most engineers debug by panicking. The skill of debugging — narrowing the search space methodically, writing down hypotheses, checking assumptions — is rarely taught and is one of the highest-leverage skills you can develop. **This is the single most generalizable skill in this entire syllabus.** Read Agans (in Phase 1, early — see the reading list) and apply his nine rules.

**The practice:** When you hit a bug this week, *don't* immediately Google it. Spend 15 minutes first writing in your notebook, working through these questions in order:

1. **What is the symptom?** Describe it in concrete terms — what input, what expected output, what actual output, on what system.
2. **Which layer am I observing the symptom at?** UI? Browser network tab? OS? Filesystem? Network wire? (This question alone solves half of debugging.)
3. **Which layer might the cause actually live at?** Often a different layer than the one where the symptom appears.
4. **What did I expect to happen, and what model of the system produced that expectation?** Naming the model is half the battle — bugs are usually a gap between your model and reality.
5. **What's the smallest reproducer?** Strip away every variable that isn't strictly needed.
6. **What would I check first if I had to bet money on the cause?** Then: what tool can I use to *observe* that layer directly, rather than guessing?

*Then* debug. Use a tool, not a theory. As Agans says: "Quit thinking and look."

**The Agans rules, internalized as a checklist** (post these somewhere visible):

1. Understand the system.
2. Make it fail.
3. Quit thinking and look.
4. Divide and conquer.
5. Change one thing at a time.
6. Keep an audit trail.
7. Check the plug.
8. Get a fresh view.
9. If you didn't fix it, it ain't fixed.

**Retrieval:**
- *Right after the bug is fixed:* write the postmortem — even for "small" bugs. Symptom, *the layer at which it manifested*, *the layer at which it actually originated*, hypotheses (in the order you tried them), actual root cause, lesson, which Agans rule(s) applied. This becomes a debugging notebook over time.
- *Monthly:* re-read the past month's debugging entries. You'll see which of your hypotheses were wrong and why — that's where your priors are miscalibrated. Add Anki cards for the most surprising root causes. Pay special attention to "symptom layer ≠ cause layer" cases — those are the most generalizable lessons.
- *Quarterly:* a meta-question — what kinds of bugs am I getting better at finding? What kinds am I still slow on? Which Agans rules do I still skip? Retrieve patterns from the notebook.

**Resources:**
- [Debugging — David Agans](https://debuggingrules.com/) — short book, the nine rules every engineer should internalize. **Read this in month 2 of Phase 1, before Kurose & Ross.** It's the meta-framework that makes everything else compound.
- [Julia Evans' debugging zines](https://wizardzines.com/zines/bite-size-command-line/) — concrete tools (strace, lsof, gdb).
- [How to be a better debugger — Bryan Cantrill talk](https://www.youtube.com/watch?v=30jNsCVLpAE) — entertaining and serious.
- [John Regehr — How to debug](https://blog.regehr.org/archives/199) — a working researcher's complement to Agans.

### Pair with your engineer, weekly

You have a co-founder building this with you. Once a week, schedule a session where you sit next to him and pair on something *he's* working on — not something you're learning, something he's actually shipping. Watch how he solves problems. Ask questions. Try to predict his next move.

**The practice:** 60–90 minutes, once a week. Camera and screen-share if remote. He drives, you observe and ask. Take notes on what you didn't understand and turn them into next week's reading or Anki cards.

**This is the highest-leverage learning hour of your week** because:
- You're watching a working engineer make decisions in real time, with real stakes.
- You're learning the actual codebase you'll one day contribute to.
- It builds the trust and language between you that makes the partnership work.
- It exposes the gap between what you've learned and what you can apply, faster than anything else.

**A specific thing to watch for:** pay attention to the *meta-moves* — when he hits something unexpected, what's the *first* thing he does? Does he reach for a particular tool? Does he reproduce in isolation? Does he check the logs at a particular layer? These habits are mostly invisible to him and copying them is the fastest way to skill transfer.

**Retrieval:**
- *Within 24 hours of the session:* write up what you saw — not as instructions, as observations. "When he saw the failing test, he ran X first instead of Y. Why?" These notes are the most concentrated learning material you'll generate.
- *Each Friday:* before this week's session, re-read last week's notes. Are there things you didn't understand that you now do? Bring the unresolved ones to today's session as questions.
- *Monthly:* skim the month of pairing notes. Identify two things he does habitually that you don't yet. Practice them in your own work that month.
- *The ultimate test:* by month 12, predict his next move during the session. By month 24, *correctly predict* his next move more than half the time. That's how you measure the closing of the gap.

By month 12, the goal is to switch — *you* drive sometimes, while he observes. By month 24, you should be opening PRs to the codebase yourself.

---

## Phase 1 — Foundations *(months 1–12)*

**Theme:** By the end of this phase, you understand what happens between you pressing a key and a pixel changing on screen — and what happens between two computers when they talk. Memory, processes, syscalls, the shell, and the network at a level most engineers never reach. You should also have internalized the meta-skill of *layered thinking*: when something behaves unexpectedly, you ask which layer is doing what, and you reach for tools that observe each layer directly.

**Note on order:** Linux and networking are taught together in this phase, deliberately. Setting up a webserver, configuring a firewall, or running gitea without understanding TCP, ports, and DNS is exactly the "doing things without knowing what's underneath" feeling we are here to dissolve. The Pi work is split into two stages — basic shell/systemd work early, and the public-facing server work later, after networking is real. Agans' *Debugging* comes early, before the technical stack, because the meta-framework it provides shapes how you absorb everything that follows.

### Core trunk

#### 1. Python Basics
Move fast through this. You already know what loops are. boot.dev is your runway, not your syllabus.

- **What:** boot.dev courses 1–7 (Python, Linux, Git, OOP, Functional). Skim chapters where you already know the material; do every exercise where you don't.
- **Resources:**
  - [boot.dev backend path](https://www.boot.dev/paths/backend)
  - [Learn to Code in Python](https://www.boot.dev/courses/learn-code-python)
  - [Learn Linux](https://www.boot.dev/courses/learn-linux)
  - [Learn Git](https://www.boot.dev/courses/learn-git)
- **Hours:** ~60

#### 2. Debugging — David Agans
Short, transformative, read it before you go deeper. 150 pages. Read in a weekend. The nine rules become the scaffolding of every debug session for the rest of your life. Doing this in month 2 means every chapter of CSAPP, every Pi failure, every weird browser behavior you encounter through the rest of the plan slots into a framework instead of being a fresh panic each time.

- **What:** Cover to cover. Hand-write the nine rules onto a card and stick it to your monitor. As you work through the rest of Phase 1, mark in the margins of your debugging notebook which rule(s) applied to each bug you fixed.
- **Resources:**
  - [Debugging — David Agans](https://debuggingrules.com/) — the book.
  - [debuggingrules.com](https://debuggingrules.com/) — also has the rules summarized and free supplementary content.
- **Hours:** ~10

#### 3. Data Structures & Algorithms
You will see these everywhere — in databases, in routing tables, in your own code. Understanding them at the level of "I have implemented this" changes how you read code forever.

- **What:** boot.dev DSA course. Every exercise. Pay attention to Big-O — it's the language engineers use to talk about performance.
- **Resources:**
  - [boot.dev DSA course](https://www.boot.dev/courses/learn-data-structures-and-algorithms-python)
  - Reference: [Introduction to Algorithms (CLRS)](https://mitpress.mit.edu/9780262046305/introduction-to-algorithms/) — only as reference, do not read cover to cover.
- **Hours:** ~50

#### 4. C & Memory Management
The course that dissolves the feeling of magic. After this, pointers, the stack, the heap, and what a process actually is will be concrete things in your head, not abstract words.

- **What:** boot.dev C memory management course. Slow down. Take notes by hand. One of the highest-leverage things in the whole plan.
- **Resources:**
  - [boot.dev C course](https://www.boot.dev/courses/learn-memory-management-c)
  - [Beej's Guide to C Programming](https://beej.us/guide/bgc/) — free, excellent, complementary.
- **Hours:** ~60

#### 5. Computer Systems: A Programmer's Perspective (CSAPP)
The book that makes you stop being scared of the layer beneath your code. Read in the morning, 30 minutes, hand-written notes.

- **What:** Chapters 1–3 (machine-level representation), 6 (memory hierarchy), 8 (exceptional control flow), 9 (virtual memory). Skip the rest unless curious.
- **Resources:**
  - [CSAPP book site](http://csapp.cs.cmu.edu/)
  - [CMU 15-213 lectures](https://www.cs.cmu.edu/~213/) — the course this book was written for, free.
  - Lab assignments: bomb lab, attack lab, malloc lab — pick at least one.
- **Hours:** ~80

#### 6. Pi Homelab — Stage 1 *(basics)*
A Linux box you control teaches you Linux. Headless, ssh-only, no shortcuts. In stage 1, you're learning the shell, systemd, and the local Pi as a Linux machine — not yet running services facing the network.

- **What:** Headless Pi setup. ssh in. Learn the shell deeply. Write your first systemd service that runs locally. Practice the things from the boot.dev Linux course on real hardware. *Don't* expose anything to the network yet. Trace at least three things on the Pi as part of the weekly tracing practice — `ls` invoking syscalls, a systemd service starting up, `apt install` doing its work.
- **Lineage detour (optional, ~5 hrs):** Read the original Unix paper — Ritchie & Thompson, "The UNIX Time-Sharing System" (1974) — and play with [Research Unix V7](https://github.com/jserv/simulavr) in an emulator for an afternoon. Modern Linux is a coral reef built on this fossil. Suddenly it makes sense why everything is a file, why the shell is a separate program, why fork/exec are two calls instead of one. Write the contrast note: what survived, what changed, what got bolted on.
- **Resources:**
  - [Raspberry Pi OS docs](https://www.raspberrypi.com/documentation/)
  - [Arch Wiki on systemd](https://wiki.archlinux.org/title/systemd) — gold standard documentation, applicable to any Linux.
  - [The Linux Command Line (Shotts)](https://linuxcommand.org/tlcl.php) — free book, deeper than boot.dev's Linux course.
  - For the lineage detour: [The UNIX Time-Sharing System (PDF)](https://www.bell-labs.com/usr/dmr/www/cacm.html) — the original 1974 paper. [The Unix Heritage Society](https://www.tuhs.org/) for emulators and source.
- **Hours:** ~20 (+5 for lineage)

#### 7. Computer Networking — Top-Down Approach
The CCNA replacement. Top-down: HTTP first, then TCP, then IP. Learning this *before* you set up gitea, nginx, or HTTPS means you'll understand what you're doing instead of copying tutorials. This is the load-bearing pillar of the "no more feeling small about infrastructure" goal.

- **What:** Chapters 1–3 deeply (application, transport, TCP). Skim 4–5. Pair with packet captures on your Pi using `tcpdump` — this is where the theory meets your hands. Do at least four traces during this module: a full DNS resolution (using `dig +trace`), a TCP three-way handshake, a TLS handshake, and a full HTTP request from browser to your Pi gitea instance.
- **Lineage detour (recommended, ~6 hrs):** Read RFC 1945 — the original HTTP/1.0 spec from 1996. It's only ~60 pages and reads like a description of a small clean protocol. Then skim the table of contents of [RFC 9110 (HTTP Semantics, 2022)](https://www.rfc-editor.org/rfc/rfc9110.html) and look at HTTP/2 and HTTP/3 at a high level. Modern HTTP is HTTP/1.0 plus thirty years of patches for problems the original didn't anticipate — head-of-line blocking, multiplexing, encryption-everywhere, server push. Write the contrast note: what stayed the same? What did each new version exist to fix? You'll never look at a `Content-Length` header the same way.
- **Resources:**
  - [Kurose & Ross — book site](https://gaia.cs.umass.edu/kurose_ross/)
  - [Stanford CS 144 lectures](https://cs144.github.io/) — free course that complements the book.
  - [High Performance Browser Networking](https://hpbn.co/) — Ilya Grigorik, free online, modern.
  - [tcpdump tutorial](https://danielmiessler.com/study/tcpdump/)
  - [Julia Evans — How DNS works zine](https://wizardzines.com/zines/dns/) — gentle starting point.
  - For the lineage detour: [RFC 1945 — HTTP/1.0](https://www.rfc-editor.org/rfc/rfc1945.html). [Daniel Stenberg — HTTP/2 explained](https://daniel.haxx.se/http2/) for a working engineer's tour of what changed.
- **Hours:** ~60 (+6 for lineage)

#### 8. Pi Homelab — Stage 2 *(real server)*
*Now* the Pi becomes a public-facing server, with you understanding every layer. This is where you set up gitea, nginx as a reverse proxy, HTTPS via Let's Encrypt, and a firewall — knowing what each one is doing at the protocol level.

- **What:** UFW firewall (knowing what packets you're filtering and why). nginx as a reverse proxy. Let's Encrypt + certbot for HTTPS (understanding TLS handshakes from Kurose). Self-hosted git with gitea. Backups to S3 via a systemd timer. Use `tcpdump` and `wireshark` to actually watch the traffic. Trace your own setup end-to-end and write the layer map to a card — this is your first real production debugging asset.
- **Resources:**
  - [DigitalOcean's guide to ufw](https://www.digitalocean.com/community/tutorials/ufw-essentials-common-firewall-rules-and-commands)
  - [nginx official docs — reverse proxy guide](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)
  - [Let's Encrypt + certbot](https://certbot.eff.org/)
  - [gitea self-hosting](https://docs.gitea.com/installation/install-from-binary)
  - [Wireshark User's Guide](https://www.wireshark.org/docs/wsug_html_chunked/)
- **Hours:** ~30

#### 9. LFCS Certification
Proof, to yourself, that the skills are real. Vendor-neutral, hands-on exam — the right kind of cert. Take it at the end of Phase 1, after both the Linux course and the networking course are behind you, with a real running Pi server as your study lab.

- **What:** Linux Foundation Certified System Administrator. Practical exam. By the time you sit it, you should be able to debug a broken service on your Pi from first principles — knowing both the systemd side and the network side.
- **Resources:**
  - [LFCS official page](https://www.linuxfoundation.org/certification/sysadmin/)
  - [Sander van Vugt's LFCS prep](https://www.sandervanvugt.com/) — widely recommended.
- **Hours:** ~50

### Optional branches

#### Text Editor in C *(branch)*
The Henley project. You don't really know how a text editor works until you've written one.

- **What:** A text editor in C. No ncurses magic. Implement gap buffer or piece table. Cursor that remembers its column. Undo/redo via command pattern.
- **Resources:**
  - [Austin Henley's post on challenging projects](https://austinhenley.com/blog/challengingprojects.html)
  - [Build Your Own Text Editor (kilo)](https://viewsourcecode.org/snaptoken/kilo/) — line-by-line tutorial, perfect starting point.
  - [The Craft of Text Editing (Finseth)](https://www.finseth.com/craft/) — free book.
- **Hours:** ~60

#### Toy DNS Resolver *(branch — strongly recommended)*
The most direct antidote to the "why isn't my hosts file blocking this site" class of confusion. Implement a DNS resolver that walks from a root server to an authoritative answer. After this, every DNS-related symptom you encounter in your career has a clear mental model behind it. Around 200–400 lines.

- **What:** A recursive DNS resolver, in Go or Python. Talks to root servers, follows referrals, parses A and AAAA records. Resolve a domain end-to-end without using your OS resolver.
- **Resources:**
  - [Implement DNS in a Weekend (Julia Evans)](https://implement-dns.wizardzines.com/) — the perfect tutorial for exactly this. Free.
  - [RFC 1035 — DNS](https://www.rfc-editor.org/rfc/rfc1035) — the original spec, surprisingly readable.
  - [How a DNS query actually works](https://jvns.ca/blog/how-updating-dns-works/) — Julia Evans on the messy reality.
- **Hours:** ~25

#### The Linux Programming Interface *(branch)*
Reference book. Use it when CSAPP or your Pi work bumps into a syscall you don't understand.

- **What:** Kerrisk. Read chapters on processes, signals, file I/O, memory mapping as needed. Not cover-to-cover.
- **Resources:**
  - [TLPI official site](https://man7.org/tlpi/)
- **Hours:** ~40 (as reference, over years)

### Phase 1 reading

- *Debugging* — David Agans *(month 2 — read first, it changes how you absorb everything else)*
- *Computer Systems: A Programmer's Perspective* — Bryant & O'Hallaron *(months 1–6)*
- *Computer Networking: A Top-Down Approach* — Kurose & Ross *(months 7–10)*
- *The Linux Programming Interface* — Kerrisk *(reference, dip in as needed)*
- [Julia Evans' zines](https://wizardzines.com/) — pay-what-you-want, illustrated, perfect for filling Linux/networking gaps. The DNS, networking, and bash zines specifically pair beautifully with this phase. **Buy *How DNS Works*, *Bite Size Networking*, and *Bite Size Linux* in month 1** — they are the tracing-practice sourcebook.
- Background dip-in: [The Pragmatic Programmer](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/) — career wisdom, read whenever.

---

## Phase 2 — Go & the Backend Toolkit *(months 13–20)*

**Theme:** Go, deeply. SQL, Docker, the building blocks of every backend you will ever write. By the end of this phase, you can build any backend service from scratch and explain every layer beneath it.

### Core trunk

#### 10. Go Fundamentals
The lingua franca of infrastructure. Kubernetes, Docker, Terraform — all Go. This is the language you'll live in.

- **What:** boot.dev Go course. Then HTTP clients course. Build the Pokedex. Pay close attention to interfaces and error handling — the two things Go does differently.
- **Lineage detour (recommended, ~6 hrs):** Read Tony Hoare's [Communicating Sequential Processes (1978)](https://www.cs.cmu.edu/~crary/819-f09/Hoare78.pdf) — the paper Go's concurrency model is named after. Just the first ten pages. Then read Russ Cox's [Bell Labs and CSP Threads](https://swtch.com/~rsc/thread/) for the line from CSP through Plan 9 to Go. Goroutines and channels stop being arbitrary language features and become a 45-year-old idea finally getting wide adoption. Write the contrast note: what does Go's `chan` keep from Hoare's CSP, and what does it modify? (Hint: buffering, select, the `close` operation.)
- **Resources:**
  - [boot.dev Learn Go](https://www.boot.dev/courses/learn-golang)
  - [boot.dev Learn HTTP Clients](https://www.boot.dev/courses/learn-http-clients-golang)
  - [A Tour of Go](https://go.dev/tour/welcome/1) — free, official.
  - [Effective Go](https://go.dev/doc/effective_go) — official idiom guide.
  - For the lineage detour: [Hoare — CSP paper (PDF)](https://www.cs.cmu.edu/~crary/819-f09/Hoare78.pdf). [Russ Cox — Bell Labs and CSP Threads](https://swtch.com/~rsc/thread/).
- **Hours:** ~80 (+6 for lineage)

#### 11. The Go Programming Language *(book)*
boot.dev teaches you to write Go. This book teaches you to think in Go.

- **What:** Donovan & Kernighan. Read alongside boot.dev Go work. Notes on places where idiom differs from your instinct.
- **Resources:**
  - [gopl.io — book site](https://www.gopl.io/)
- **Hours:** ~50

#### 12. SQL & Databases
Your booking system runs on Postgres. Your understanding of indexes, joins, and normalization will determine whether it scales.

- **What:** boot.dev SQL course. Build the Blog Aggregator. Pay attention to query plans — `EXPLAIN` is your friend. Use the tracing practice on Postgres: trace a query from `psql` through the wire protocol to query parsing to plan to execution.
- **Lineage detour (recommended, ~5 hrs):** Read Codd's [A Relational Model of Data for Large Shared Data Banks (1970)](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf). Twelve pages. Predates SQL by years. The paper that defines what a *relation* is, what *normal form* means, and why joins are not arbitrary. Modern SQL is a deliberately impure implementation of Codd's ideas — you'll read both the elegance of the original and the compromises every database has had to make. Pair with [Joe Celko's "What's Wrong With SQL"](https://www.red-gate.com/simple-talk/databases/sql-server/learn/celko-on-sql-relational-aspects/) for the contrast in voice. Write the contrast note: what does Codd's model insist on that SQL violates? Why?
- **Resources:**
  - [boot.dev Learn SQL](https://www.boot.dev/courses/learn-sql)
  - [boot.dev Blog Aggregator project](https://www.boot.dev/courses/build-blog-aggregator-golang)
  - [PostgreSQL tutorial](https://www.postgresqltutorial.com/) — free.
  - [Use The Index, Luke](https://use-the-index-luke.com/) — free book on SQL indexing. Underrated.
  - For the lineage detour: [Codd — A Relational Model of Data (PDF)](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf).
- **Hours:** ~40 (+5 for lineage)

#### 13. HTTP Servers in Go
Routing, JSON, auth, webhooks. This is where you start to feel like a real backend engineer. You already understand HTTP at the protocol level from Phase 1's networking work — now you build the server side.

- **What:** boot.dev HTTP Servers course. Build it from chapter exercises up. Read the `net/http` source while you do.
- **Resources:**
  - [boot.dev Learn HTTP Servers](https://www.boot.dev/courses/learn-http-servers-golang)
  - [`net/http` source](https://pkg.go.dev/net/http) — read the actual standard library.
- **Hours:** ~60

#### 14. Docker, S3 & CDN
The ops side of the booking system. File storage, CDN delivery, containerization. You already use these at work; now you'll know them.

- **What:** boot.dev Docker course + S3/CloudFront course. Containerize the blog aggregator. Push it to your Pi. Trace `docker run` end-to-end as part of the tracing practice — image pull, namespaces, cgroups, runtime. This is the moment Docker stops being magic.
- **Lineage detour (recommended, ~8 hrs, *especially valuable* if you also do the toy container runtime branch):** Read [Plan 9 from Bell Labs — "The Use of Name Spaces in Plan 9"](https://9p.io/sys/doc/names.html) by Pike, Presotto, Thompson, et al. Twelve pages. Plan 9 invented per-process namespaces in the late 80s; Linux namespaces (the foundation of every container) are a direct descendant. Then read [LWN's Linux namespaces overview](https://lwn.net/Articles/531114/) to see how the idea was adapted. After this, the Linux `unshare` syscall is not magic — it's a specific borrowing from Plan 9, and you can articulate exactly which design choices were kept and which were changed. Containers stop being a Docker concept and become a kernel concept that Docker happens to package nicely.
- **Resources:**
  - [boot.dev Learn Docker](https://www.boot.dev/courses/learn-docker)
  - [boot.dev File Servers and CDNs](https://www.boot.dev/courses/learn-file-servers-s3-cloudfront-golang)
  - [Docker official docs](https://docs.docker.com/get-started/)
  - For the lineage detour: ["The Use of Name Spaces in Plan 9"](https://9p.io/sys/doc/names.html). [Plan 9 papers index](https://9p.io/sys/doc/) for further wandering. [Linux namespaces overview (LWN)](https://lwn.net/Articles/531114/).
- **Hours:** ~50 (+8 for lineage)

### Optional branches

#### Tiny HTTP Server from raw TCP *(branch)*
Write an HTTP server without using `net/http`. After this, HTTP is bytes on a wire, not a black box.

- **What:** ~300 lines of Go. Listen on a TCP port. Parse the request line and headers yourself. Handle keep-alive. Then read the real `net/http` source.
- **Resources:**
  - [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html)
  - [Build Your Own X — HTTP server section](https://github.com/codecrafters-io/build-your-own-x#build-your-own-web-server)
  - [Codecrafters HTTP Server challenge](https://app.codecrafters.io/courses/http-server) — paid but excellent.
- **Hours:** ~30

#### Toy Container Runtime *(branch)*
Linux namespaces and cgroups demystified. After this, Docker is not magic — you know what it's doing because you did 5% of it yourself. Pairs especially well with the Plan 9 namespaces lineage detour above.

- **What:** ~500 lines of Go. PID, mount, network namespaces. cgroups for resource limits. chroot.
- **Resources:**
  - [Liz Rice — "Containers from Scratch" talk](https://www.youtube.com/watch?v=8fi7uSYlOdc) — the entry point.
  - [Liz Rice's `containers-from-scratch` repo](https://github.com/lizrice/containers-from-scratch)
  - [Linux namespaces overview (LWN)](https://lwn.net/Articles/531114/) — classic series.
  - [cgroups v2 docs](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- **Hours:** ~50

### Phase 2 reading

- *The Go Programming Language* — Donovan & Kernighan *(months 14–18)*
- *TCP/IP Illustrated, Vol 1* — Stevens *(reference, when networking questions deepen)*
- Background: [Go blog](https://go.dev/blog/) — read 2–3 posts a week, especially the ones from Russ Cox.

---

## Phase 3 — Distributed Systems & the Booking System *(months 21–30)*

**Theme:** Build the rental booking system at scale. Read DDIA. Learn distributed systems by feeling the problems in your hands.

### Core trunk

#### 15. Pub/Sub Architecture
How systems talk to each other when one cannot wait for the other. Booking confirmations, payment events, notifications — all async.

- **What:** boot.dev RabbitMQ course. Build the project. Understand at-least-once vs exactly-once delivery and why the former is reality.
- **Resources:**
  - [boot.dev Learn Pub/Sub](https://www.boot.dev/courses/learn-pub-sub-rabbitmq-golang)
  - [RabbitMQ tutorials](https://www.rabbitmq.com/getstarted.html)
  - [Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/) — the canonical reference, free site.
- **Hours:** ~40

#### 16. Designing Data-Intensive Applications (DDIA)
The most important book on this list. Slowly, with hand-written notes, over four months. Will permanently change how you think about backends.

- **What:** Kleppmann. All chapters. Especially 5 (replication), 6 (partitioning), 7 (transactions), 8 (the troubles), 9 (consistency and consensus).
- **Lineage detour, embedded (recommended, ~10 hrs spread over the chapters):** DDIA already cites foundational papers at the end of every chapter. *Frame those reading sessions explicitly as lineage work* rather than optional follow-ups. The most valuable two: read [Dynamo — Amazon's Highly Available Key-value Store (2007)](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf) before chapter 5 (replication) — this paper is the ancestor of every NoSQL system you will ever touch. And read [The Google File System (2003)](https://research.google/pubs/pub51/) before chapter 10 (batch processing). Write contrast notes: what assumptions did Dynamo make that Postgres rejects? What tradeoffs did GFS choose that S3 inherits and HDFS doesn't?
- **Resources:**
  - [DDIA — book site](https://dataintensive.net/) — includes a glossary of references.
  - [Martin Kleppmann's talks](https://www.youtube.com/results?search_query=martin+kleppmann)
  - For the lineage detours: [Dynamo paper](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf), [GFS paper](https://research.google/pubs/pub51/). The full citation list at the end of each DDIA chapter is the lineage map for that chapter — use it.
- **Hours:** ~100 (lineage already counted)

#### 17. Building Microservices (Sam Newman)
Read this while you architect the booking system. Newman will be in your ear during every service-boundary decision.

- **What:** Newman 2nd ed. Read chapters relevant to current architectural decisions, not in order.
- **Resources:**
  - [Sam Newman — Building Microservices, 2nd ed](https://samnewman.io/books/building_microservices_2nd_edition/)
  - [Sam Newman's talks](https://samnewman.io/talks/) — companion content.
- **Hours:** ~50

#### 18. Release It! (Michael Nygard)
How systems fail in production. Read before you deploy seriously. Short, gripping, full of horror stories you will not want to repeat.

- **What:** Cover to cover. Apply the patterns to your booking system: timeouts, circuit breakers, bulkheads, graceful degradation.
- **Resources:**
  - [Release It! 2nd ed](https://pragprog.com/titles/mnee2/release-it-second-edition/)
- **Hours:** ~30

#### 19. The Rental Booking System
The whole point. Built slowly, with each component understood. This is what your business rests on.

- **What:** Vendor + user portals. Go API. Postgres + Redis. RabbitMQ for async. S3 + CloudFront for media. Stripe (test mode) for payments. Deployed on AWS via Terraform. Observability from day one.
- **Resources:**
  - [Stripe API docs](https://stripe.com/docs/api)
  - [Terraform docs](https://developer.hashicorp.com/terraform/docs)
  - [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
  - [Designing the Schema](https://use-the-index-luke.com/) — for the booking conflict resolution piece specifically.
  - [Distributed locks with Redis](https://redis.io/docs/latest/develop/use/patterns/distributed-locks/) — relevant for the double-booking problem.
- **Hours:** ~250

#### 20. AWS Solutions Architect Associate
Studying for this after you've deployed a real system on AWS makes the cert easy and the knowledge stick. Right cert, right time.

- **What:** Adrian Cantrill's course. Practice exams. Take the exam within 2 weeks of finishing the course while it's fresh.
- **Resources:**
  - [AWS SAA-C03 official](https://aws.amazon.com/certification/certified-solutions-architect-associate/)
  - [Adrian Cantrill's SAA course](https://learn.cantrill.io/p/aws-certified-solutions-architect-associate-saa-c03) — gold standard.
  - [Tutorials Dojo practice exams](https://tutorialsdojo.com/aws-certified-solutions-architect-associate-saa-c03/) — best practice tests.
- **Hours:** ~80

### Optional branches

#### KV Store with Replication *(branch)*
DDIA chapter 5 in code form. Two nodes, leader-follower replication, handle a leader failure. The "I get distributed systems" project.

- **What:** ~800 lines of Go. Leader handles writes, replicates to follower. Implement a heartbeat. Then unplug the leader and watch it fail correctly.
- **Resources:**
  - DDIA chapter 5 (the only resource you need; the project is *applying* the book).
  - [bitcask paper](https://riak.com/assets/bitcask-intro.pdf) — simplest possible storage engine, ~30 pages.
  - Reference implementation: [BoltDB source](https://github.com/etcd-io/bbolt) — readable Go.
- **Hours:** ~60

#### Implement Raft *(branch — heavy commitment)*
The big one. After this you do not feel small about distributed systems anymore. Heavy time investment — only if the curiosity is real.

- **What:** MIT 6.824 Lab 2. The paper, the visualization, then the code. Expect this to be hard. Plan for 100+ hours.
- **Resources:**
  - [The Secret Lives of Data — Raft visualization](http://thesecretlivesofdata.com/raft/) — start here.
  - [The Raft paper (PDF)](https://raft.github.io/raft.pdf) — "In Search of an Understandable Consensus Algorithm."
  - [raft.github.io](https://raft.github.io/) — official home, list of implementations.
  - [MIT 6.824 course](https://pdos.csail.mit.edu/6.824/) — the labs are public; lab 2 is the canonical "implement Raft."
  - [Diego Ongaro's PhD thesis](https://web.stanford.edu/~ouster/cgi-bin/papers/OngaroPhD.pdf) — extended version of the paper.
- **Hours:** ~120

### Phase 3 reading

- *Designing Data-Intensive Applications* — Kleppmann *(months 21–26, slowly)*
- *Building Microservices, 2nd ed* — Sam Newman *(months 24–28, as reference during architecture)*
- *Release It!* — Michael Nygard *(month 28, before serious deployment)*
- Papers — read at least one per month, framed as lineage work where applicable:
  - [Dynamo — Amazon's Highly Available Key-value Store](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf) *(ancestor of every NoSQL system)*
  - [Spanner — Google's Globally-Distributed Database](https://research.google/pubs/pub39966/)
  - [The Google File System](https://research.google/pubs/pub51/) *(ancestor of HDFS, S3's design assumptions)*
  - [MapReduce](https://research.google/pubs/pub62/) *(ancestor of Spark, Beam, every batch framework)*

---

## Phase 4 — Kubernetes, Observability, Synthesis *(months 31–39)*

**Theme:** Now that you've built distributed systems, learn how the orchestration layer actually works. Master observability. Synthesize and write.

### Core trunk

#### 21. Kubernetes the Hard Way
No managed Kubernetes, no `kubeadm`. Set it up from binaries on your Pi cluster. After this, K8s components are real things, not magic.

- **What:** Kelsey Hightower's tutorial, adapted for Pis. etcd, kubelet, kube-apiserver, kube-scheduler — set them up by hand. Trace `kubectl apply` end-to-end as part of the tracing practice — this single trace, written down, becomes one of the most useful Anki cards you have for the rest of your career.
- **Lineage detour (strongly recommended, ~6 hrs):** Read [Borg — Large-scale cluster management at Google with Borg (Verma et al., 2015)](https://research.google/pubs/pub43438/). Borg is the system Kubernetes was built to be the open-source successor to. The paper describes a decade of operating production schedulers at Google scale, with lessons K8s explicitly inherits and lessons it explicitly rejects. Kubernetes makes ten times more sense as "Borg with the rough edges filed down" than it does read cold from the K8s docs. Write the contrast note: what did K8s keep (the controller pattern, declarative state, the scheduler's bin-packing approach)? What did it deliberately change (RBAC, namespaces, CRDs as user-facing extension points)? Why?
- **Resources:**
  - [Kubernetes the Hard Way (Kelsey Hightower)](https://github.com/kelseyhightower/kubernetes-the-hard-way)
  - [k3s for Pi](https://k3s.io/) — once you've done it the hard way, this is what you'll actually run.
  - [Kubernetes the Hard Way on bare metal](https://github.com/mmumshad/kubernetes-the-hard-way) — Mumshad's adapted version.
  - [Kubernetes Up & Running, 3rd ed](https://www.oreilly.com/library/view/kubernetes-up-and/9781098110192/) — Burns, Beda, Hightower.
  - For the lineage detour: [Borg paper (PDF)](https://research.google/pubs/pub43438/). Optional follow-up: [Omega paper](https://research.google/pubs/pub41684/) — Borg's intermediate successor at Google, which fed into K8s' design.
- **Hours:** ~60 (+6 for lineage)

#### 22. Observability
You cannot run what you cannot see. Logs, metrics, traces. SLOs and error budgets. The skill that separates "deployed" from "operated." This is the *systematized* form of the tracing practice — the same instinct, but built into your production system instead of done by hand.

- **What:** Add Prometheus + Grafana + OpenTelemetry to the booking system. Define SLOs. Run a chaos experiment. Write a postmortem when it breaks.
- **Resources:**
  - [Google SRE book](https://sre.google/sre-book/table-of-contents/) — free. Read SLO, error budgets, postmortems chapters.
  - [Google SRE Workbook](https://sre.google/workbook/table-of-contents/) — free. Practical companion.
  - [Prometheus docs](https://prometheus.io/docs/introduction/overview/)
  - [Grafana tutorials](https://grafana.com/tutorials/)
  - [OpenTelemetry](https://opentelemetry.io/docs/)
  - [Distributed Systems Observability (Sridharan)](https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/) — short, free online.
- **Hours:** ~80

#### 23. Synthesis — Writing & Polish
The receipts. Six to ten blog posts about what you actually built. This is the moment imposter syndrome dissolves, not when you finish reading.

- **What:** Six to ten posts. Public, your real name. Architecture diagrams. README every project. Polish your GitHub.
- **Resources:**
  - [Patrick McKenzie — Don't Call Yourself a Programmer](https://www.kalzumeus.com/2011/10/28/dont-call-yourself-a-programmer/) — career advice that frames the writing.
  - [Julia Evans on writing](https://jvns.ca/blog/2016/05/22/how-i-write-blog-posts/) — practical, low-bar.
  - [Excalidraw](https://excalidraw.com/) for diagrams.
- **Hours:** ~80

### Optional branches

#### CKA Certification *(branch)*
Optional. Hands-on K8s exam. Worth doing only if you found you genuinely love K8s. Otherwise skip.

- **What:** Certified Kubernetes Administrator. Practical exam, well-respected.
- **Resources:**
  - [CKA official](https://www.cncf.io/training/certification/cka/)
  - [Mumshad's CKA course on KodeKloud](https://kodekloud.com/courses/certified-kubernetes-administrator-cka/) — widely considered the best.
  - [killer.sh](https://killer.sh/) — the exam simulator that comes with the cert is essential.
- **Hours:** ~50

#### Toy Scheduler *(branch)*
Watch a directory of YAML, schedule "containers" across "nodes." Then read kube-scheduler source and see how the grown-up version does it.

- **What:** ~200 lines of Go. Goroutines as fake nodes is fine to start. Then make it real if curious.
- **Resources:**
  - [kube-scheduler source](https://github.com/kubernetes/kubernetes/tree/master/pkg/scheduler) — the reference implementation.
  - [Writing a custom scheduler](https://kubernetes.io/docs/tasks/extend-kubernetes/configure-multiple-schedulers/) — official docs.
- **Hours:** ~40

### Phase 4 reading

- *Kubernetes Up & Running* — Burns, Beda, Hightower *(months 31–33)*
- Kubernetes source code — kubelet and scheduler are most accessible *(months 32–35)*
- *Site Reliability Engineering* — Google *(months 34–36)*
- *A Philosophy of Software Design* — Ousterhout *(months 36–37)* — short, dense, brilliant.
- Re-read DDIA *(months 37–39)* — chapters that hit differently now.

---

## Declined paths

These are explicitly *not* on the plan. Listed here as record of the decision, not as omissions.

### CCNA *(declined)*
Cisco-specific config and spanning tree are not on the path. Kurose & Ross gives the networking knowledge that actually applies to a backend engineer / founder. Revisit only if you go work for a network-equipment company.

### OS from Scratch *(declined for now)*
Beautiful project — building a small operating system from boot to userspace. But it's a year-long rabbit hole, and CSAPP gets you understanding without the kernel-hacking commitment. Revisit at year 4+ if curiosity remains.

- For when you do: [Operating Systems: Three Easy Pieces](https://pages.cs.wisc.edu/~remzi/OSTEP/) — free book, the right starting point.
- [Stephen Marz — Making a RISC-V OS in Rust](http://osblog.stephenmarz.com/index.html)

### Write a Compiler *(declined for now)*
Crafting Interpreters is wonderful and the project is famous, but it doesn't serve the booking system or the business. Revisit at year 3+ if filmmaking tooling needs a DSL.

- For when you do: [Crafting Interpreters](https://craftinginterpreters.com/) — free online, gold standard.
- [Write an Interpreter in Go (Thorsten Ball)](https://interpreterbook.com/) — paid but excellent.

### Frontend Mastery *(declined)*
Your engineer handles this for the booking platform, and your filmmaking eye is enough for the visuals. Become competent enough to evaluate, not expert enough to build.

### Learning Elm to understand frontend frameworks *(declined)*
Tempting (the Bubble Tea README points there, and the lineage *is* real — the Elm Architecture is the cleanest ancestor of modern reducer-based state management). But Elm isn't on the path of the booking system, the filmmaking tools, or systems competence. The instinct to chase this is the *Lineage, not regress* trap in its purest form: "I can't really understand X until I learn Y." A bounded version — read the Elm Architecture guide for an afternoon if you ever do go deep on Bubble Tea — is fine; learning Elm as a language is not on this plan. Revisit at year 4+ only if functional programming has independently become a love.

### LeetCode-style algorithm grinding *(declined)*
The DSA course gets you to working-engineer level. FAANG-style competitive programming is a separate skill and not on this path.

---

## Background reading — lifetime, no rush

These can be read any time. Dip into them whenever the main reading needs a break.

- [The Pragmatic Programmer](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/) — Hunt & Thomas. Career wisdom.
- [A Philosophy of Software Design](https://web.stanford.edu/~ouster/cgi-bin/book.php) — Ousterhout. Short, dense, brilliant on complexity.
- [The Mythical Man-Month](https://en.wikipedia.org/wiki/The_Mythical_Man-Month) — Brooks. Software project management, still relevant 50 years later.
- [Julia Evans' zines](https://wizardzines.com/) — illustrated, concrete, joyful.
- [Dan Luu's blog](https://danluu.com/) — long-form analyses of how systems actually fail in industry.
- [Brendan Gregg's blog](https://www.brendangregg.com/) — performance, observability, the real Linux.
- [Papers We Love](https://paperswelove.org/) — the canonical lineage map for computer science. Use it when a flagged lineage detour finishes and you want to keep reading.

---

## What you'll be at the end

You will have:

- A real, deployed, scaled rental booking system that you wrote.
- A text editor in C *(if you took the branch)*.
- A toy DNS resolver, a toy HTTP server, a toy container runtime, a KV store with replication, possibly a Raft implementation.
- A homelab on Pis running services you built and operate.
- LFCS and AWS SAA, possibly CKA.
- A blog with 6–10 posts in your name, including a few "lineage" posts that are rare and disproportionately valuable.
- A GitHub that tells a story.
- Notebooks full of hand-written notes — including a debugging notebook three years deep, ~150 layer-by-layer system traces, and a small but valuable collection of one-page lineage contrast notes.
- An Anki deck of ~2,000 cards, including layer maps for every major system you regularly touch and lineage-contrast cards that encode *why* features exist.

In skill terms: a senior-level backend engineer with rare DevOps depth, comfortable from the bare metal up to the cluster orchestrator, fluent in Go, capable of architecting and operating real distributed systems. The kind of engineer who, when something breaks at 3am, can reason about it from first principles instead of guessing — because you have spent three years building the habit of asking *which layer is misbehaving and what tool will let me see it directly*. And the kind of engineer who, when a new framework appears, can recognize what it inherits and what it innovates instead of treating it as another opaque novelty.

In imposter-syndrome terms: the feeling of "I'm using things I don't understand underneath" should be substantially gone, because you will have built — at small scale, with your own hands — most of the layers underneath, and you have a reflexive practice of looking beneath whenever something surprises you.

In founder terms: you will be able to sit next to your engineer and pair on hard problems, and your contributions will be substantive — not just product-level. You'll be able to evaluate the architecture decisions an agentic system proposes. You'll be able to ship the technical parts of your business yourself when you need to.

---

*Plan adopted: April 2026.*
*Plan target completion: July 2029.*
*Plan owner: [your name].*

*The plan is allowed to evolve, but only at month boundaries. Decisions logged in the field notes.*
