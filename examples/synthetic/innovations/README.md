# Fictional OHLC innovation corpus

This corpus is deliberately fictional. It supplies a 12-session by two-security
primitive qualification grid, not a qualified market history or 1,260-session fit.
Sessions are consecutive synthetic UTC days, with an explicitly declared fictional
calendar; they are not exchange trading sessions. Column order is frozen.

[inputs.json](inputs.json) preserves source decimal strings, coordinates, cutoff,
return convention, raw OHLC, compatible adjustment vintage and construction/action
attestations with SHA-256 identities. The split row stipulates prior raw close 100,
2-for-1 split and current flat prices 50. The dividend row stipulates prior raw
close 100, dividend 1 and current flat prices 99. Both already have total return
zero. Other rows stipulate compatible returns/prices and no actions. These are
construction claims, not independently established market-provider evidence.

[reference.json](reference.json) freezes the expected ready status, shape/order,
decimal units and R1 constants. Its per-row synthetic close, proxy and innovation
digits come from literal equations evaluated with Decimal at 90 digits and checked
against 110 digits. The separate reference expressions never call the component.
It also retains E07 toy constants separately from R1, E08 price-only refusal, E01,
E02, the exact five-observation stack case and fixed-state R1 seed/variance/Gaussian
NLL/one-through-21-step expectations for each IDR column. Forecast origin is after
the final scored observation; fixed parameters are stipulated, not fitted.

The [qualification script](../../../scripts/qualify_innovations.py) checks source
attestations, input/reference hashes, the frozen specification and comparisons.
Its default operation reads the frozen corpus and refuses disagreement; it does
not rewrite expectations. `--write-reference` is an explicit corpus-authoring
operation. Binary64 comparisons use predeclared `rtol=1e-8`, `atol=1e-12` with
reference-price scale for preceding close and scale one for decimal proxy/x.
Ninety digits leave substantial headroom over the derived binary64 calculation;
110-digit row re-evaluation agrees within `1e-85 * max(1, abs(reference))`.

The [component](../../../src/prosper/innovations.py) always consumes decimal simple
total returns. Its explicitly selected percent-output experiment multiplies x by
100 and proxy by 10,000 and records reciprocal kappa 100. Returns-only `x=r` is a
separate identity with the same input-integrity requirements. Invalid inputs have
located issues, retained source rows and no partial analytical matrices. Valid
zero rows remain; unusable whole series are reported to the later fitter. This
boundary supports explicitly fictional UTC inputs only; metadata consistency does
not establish historical identity, action truth or calendar completeness.

Same-agent direct-expression evidence does not satisfy independent model review,
G1-G3, forward calibration, financial use or release. Volatility fitting is a
separate child; there is no optimizer, API, provider/cache or broker integration.
