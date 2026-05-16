#!/usr/bin/env node
// Regenerates data/repos.json from the §11 seed table, padded with placeholder
// fields so the result passes scripts/validate.mjs non-strict.
// Throwaway: step 5 (curation) replaces this with hand-written content.

import { writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

// [id, name, primary theme, [secondary themes], difficulty, ref?]
const SEED = [
  ["boltdb",          "boltdb/bolt",                                  "databases",          ["storage"],              2, "v1.3.1"],
  ["groupcache",      "golang/groupcache",                            "distributed-systems",[],                       2],
  ["redis-early",     "antirez/redis",                                "databases",          [],                       3, "1.0.0"],
  ["sqlite",          "sqlite (amalgamation)",                        "databases",          [],                       5],
  ["git-early",       "git/git",                                      "version-control",    [],                       4, "v0.99"],
  ["ripgrep",         "BurntSushi/ripgrep",                           "cli-tools",          ["search"],               3],
  ["fzf",             "junegunn/fzf",                                 "cli-tools",          ["search"],               2],
  ["kube-scheduler",  "kubernetes/kube-scheduler",                    "scheduling",         ["distributed-systems"],  4],
  ["etcd-raft",       "etcd-io/raft",                                 "distributed-systems",[],                       4],
  ["fluent-bit",      "fluent/fluent-bit",                            "networking",         [],                       3],
  ["nginx",           "nginx/nginx",                                  "networking",         [],                       4],
  ["lua",             "lua/lua",                                      "runtime",            ["language"],             4],
  ["sqlite-utils",    "simonw/sqlite-utils",                          "cli-tools",          ["databases"],            1],
  ["miniredis",       "alicebob/miniredis",                           "databases",          [],                       2],
  ["tinygrad",        "tinygrad/tinygrad",                            "ml-infra",           [],                       4],
  ["llama-cpp",       "ggerganov/llama.cpp",                          "ml-infra",           [],                       4],
  ["whisper-cpp",     "ggerganov/whisper.cpp",                        "ml-infra",           [],                       3],
  ["openzfs-arc",     "openzfs/zfs (ARC)",                            "storage",            [],                       5],
  ["cpython-dict",    "python/cpython (Objects/dictobject.c)",        "runtime",            ["language"],             4],
  ["v8-ignition",     "v8/v8 (Ignition)",                             "compilers",          ["runtime"],              5],
  ["llvm-mem2reg",    "llvm/llvm-project (mem2reg)",                  "compilers",          [],                       4],
  ["postgres-exec",   "postgres/postgres (executor)",                 "databases",          [],                       5],
  ["duckdb-planner",  "duckdb/duckdb (planner)",                      "databases",          ["compilers"],            4],
  ["chibicc",         "rui314/chibicc",                               "compilers",          ["language"],             3],
  ["crafting-interp", "munificent/craftinginterpreters (tree-walker)","language",           ["compilers"],            2],
  ["litestream",      "benbjohnson/litestream",                       "databases",          ["storage"],              3],
  ["mosh",            "mobile-shell/mosh",                            "networking",         [],                       3],
  ["tigerbeetle-vsr", "tigerbeetle/tigerbeetle (vsr.zig)",            "distributed-systems",["databases"],            4],
  ["tailscale-tsnet", "tailscale/tailscale (tsnet)",                  "networking",         [],                       3],
  ["age",             "FiloSottile/age",                              "crypto",             ["cli-tools"],            2],
  ["busybox-cat",     "busybox/busybox (coreutils/cat.c)",            "unix-tools",         ["cli-tools"],            1],
  ["busybox-wc",      "busybox/busybox (coreutils/wc.c)",             "unix-tools",         ["cli-tools"],            1],
  ["gnu-grep",        "gnu/grep",                                     "unix-tools",         ["search"],               2, "v2.5.1"],
  ["netcat-hobbit",   "Hobbit netcat (nc110)",                        "networking-tools",   ["networking","cli-tools"], 2],
  ["openbsd-ping",    "openbsd/src (ping.c)",                         "networking-tools",   ["networking"],           3],
  ["curl",            "curl/curl",                                    "networking-tools",   ["networking","cli-tools"], 4],
  ["xv6",             "mit-pdos/xv6-riscv",                           "runtime",            ["operating-systems"],    2],
  ["busybox-init",    "busybox/busybox (init.c)",                     "unix-tools",         ["operating-systems"],    3],
  ["openssh-kex",     "openssh/openssh-portable (kex.c, kexgen.c)",   "networking",         ["crypto"],               5],
  ["musl-printf",     "musl/musl (src/stdio/vfprintf.c)",             "runtime",            ["language"],             4],
  ["dnsmasq",         "simonkelley/dnsmasq",                          "networking",         ["networking-tools"],     3],
];

const repos = SEED.map(([id, name, primary, secondary, difficulty, ref]) => {
  const base = { id, name, url: "https://example.com/stub" };
  if (ref) base.ref = ref;
  return {
    ...base,
    language: "stub",
    themes: [primary, ...secondary],
    difficulty,
    why: "stub",
    entry_points: [
      { label: "stub entry point", files: ["TBD"], question: "stub" },
    ],
    reading: [],
  };
});

const out = resolve(root, "data/repos.json");
writeFileSync(out, JSON.stringify(repos, null, 2) + "\n");
console.log(`wrote ${repos.length} entries → ${out}`);
