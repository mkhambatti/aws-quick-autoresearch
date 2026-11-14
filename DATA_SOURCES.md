# Data attribution and provenance

Dataset: **Data Expo 2009: Airline on time data**, Harvard Dataverse, V1, DOI https://doi.org/10.7910/DVN/HG7NV7 . The records originate from US Bureau of Transportation Statistics reporting-carrier on-time data.

Downloaded file: https://www.stat.ucdavis.edu/~duncan/Data/rdatasciencecases/Airline/2008.csv.bz2

Mirror index: https://www.stat.ucdavis.edu/~duncan/Data/rdatasciencecases/Airline/

The included experiment uses one year, **2008**, with **7,009,728 rows**, not thirty years and not every flight operated by every US carrier. No records are duplicated or synthetically expanded to claim scale. Date/delay data are historical and should not guide current travel decisions.

- Archive size: 113,753,229 bytes.
- Decompressed CSV size: 689,413,344 bytes.
- Archive SHA-256: `cc1fab9ada5ae6a879c00fa102340d0359d1ff25c9630895c054fe69c2aa9f92`.
- CSV SHA-256: `6e9306a0180790f734b2c3ce56d3feb238d4f2b64a14396833046fd01c4dfa9b`.

The original data is downloaded on demand, not redistributed in this repository. The MIT code license does not apply to third-party data; consult the original publisher's terms for reuse. Aggregated benchmark reports and SQL are included.

Data semantics: missing `NA` arrivals stay null; cancelled and diverted flights remain represented. Dashboard delay rates should use `observed_arrivals` as their denominator. Counts and integer sums are verified instead of relying on rounded averages. A dashboard can derive mean delay and cancellation rates from these sufficient statistics.
