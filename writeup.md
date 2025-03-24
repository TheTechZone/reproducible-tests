# Reproducible Builds for Signal

> TODO

> this does not aim to be a comprehnesive description on the topic of reproducible builds, android build internals or other [] / we assume the reader has a general familiriarity with the topic. we provide a general overview of our findings and recomandation. more information will be added on a rolling basis, however for questions you can reach directly the authors.


# key summary

we were unable to "fully" (i.e. as per  the [documentation](./repproducible-signal.md)) reproduce any build of signal from 7.25.0 onwards, and we suspect the issue might have exited for longer[^to-be-validated].
- part of the issues can be explained away by discrepancies in tooling (Google Play having a disjoing way of exposing apks.) the comparison script should take that into account of attempt to mitigate it.
- most concerning difference is in the dex order sensitvity: the same application, built under the same conditons ends up with differntly ordered classes.dex files. we expect this is due to file-order sensitivity and we show how using [disorderfs] can


<!-- - yo app ain't no reproducible... partly ya fault <3  -->


<!-- [^to-be-validated]: to be validated at a later moment -->


# background

---

- little historical summary (***copy from my nb and the email perringo sent***)
  - signal added repro builds {at some point}
  - issues with reproduciblity since meh ago
  - github issue threadds left hanging for a while etc

---

- what we tried so far?
  - using `v7.25.0` ? onwards - we failed to reproduce the `PlayStore` version of Signal-android (we did not attempt those)
  - testing on diffrent machines yieled inconsitent results, but they would be reproducible, none of the different local results would match playstore
  - decided to automate the build step (to remove human eror) and attempt to isolate as much of the well [known sources of nonditerminism](https://teamusec.de/pdf/conf-oakland-fourne23.pdf) plaguing software such as timestamps, randomness and metadata
    - android development ecosystem is somewhat opaque, so certain information is based on information collected from sources of various degrees of reliability and our heuristics. we have not attempted to match academic rigor, but if
  - we automate the [building process](./build-signal.py) for a given git tag. in the presence of a usb-connected android device, it will also perform the comparison attempt using the [apkdiff.py](#)
  - subsequently, we perform each build inside an dispoable QEMU vm cloned from the same base config

---
