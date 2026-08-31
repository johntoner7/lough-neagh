export default function MethodologyPage() {
  return (
    <div className="methodology-page">
      <div className="methodology-content">
        <a href="/" className="methodology-back">← Back to map</a>

        <h1 className="methodology-title">Methodology</h1>

        <section className="methodology-section">
          <h2>What This Tool Shows</h2>
          <p>
            This tool maps 35 years of river phosphorus monitoring across Northern Ireland, from
            1990 to 2024, using data obtained from DAERA under Freedom of Information. It covers
            1,201 monitoring stations and roughly 170,000 individual readings. Most monitored
            rivers are Lough Neagh tributaries, making their phosphorus concentrations directly
            relevant to the lake's current "Bad" ecological classification under the Water
            Framework Directive.
          </p>
          <p>
            The tool shows concentration (mg/l of soluble reactive phosphorus), not load. Without
            flow data, the total amount of phosphorus entering the system cannot be calculated;
            only what was measured at the sampling point on each occasion is recorded. This limits
            comparison between high-flow and low-flow catchments.
          </p>
        </section>

        <section className="methodology-section">
          <h2>Data Sources</h2>
          <div className="methodology-table-wrap">
            <table className="methodology-table">
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Source</th>
                  <th>Period</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>River nutrient readings</td>
                  <td>DAERA FOI 26-57</td>
                  <td>1990–2024</td>
                  <td>Monthly P(SOL), NO3-N per station; coverage varies by year</td>
                </tr>
                <tr>
                  <td>WFD monitoring sites</td>
                  <td>UK Environment Agency / DAERA</td>
                  <td>Current</td>
                  <td>Point geometries; unmatched stations fall back to FOI coordinates</td>
                </tr>
                <tr>
                  <td>WFD river water bodies</td>
                  <td>UK Environment Agency</td>
                  <td>2016</td>
                  <td>Catchment polygon boundaries</td>
                </tr>
                <tr>
                  <td>WFD lake classifications</td>
                  <td>DAERA / UK EA</td>
                  <td>2024 only</td>
                  <td>No historical classification available</td>
                </tr>
                <tr>
                  <td>Farm census (ward level)</td>
                  <td>NISRA</td>
                  <td>2015–2024</td>
                  <td>Cattle, sheep, pigs, area per ward; zeros treated as no-data</td>
                </tr>
                <tr>
                  <td>Ward boundaries</td>
                  <td>Ordnance Survey NI</td>
                  <td>2012</td>
                  <td>Do not align with hydrological catchments</td>
                </tr>
                <tr>
                  <td>Storm overflow spills</td>
                  <td>NI Water Corporate Asset Register</td>
                  <td>Nov 2025 snapshot</td>
                  <td>
                    Modelled, not measured. 2,433 assets, of which 1,232 have no estimate —
                    modelling covers only the most densely populated areas
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section className="methodology-section">
          <h2>How the Metrics Are Calculated</h2>
          <dl className="methodology-dl">
            <dt>Annual mean P(SOL)</dt>
            <dd>
              All non-null, positive readings for a station in a calendar year, averaged. Years
              with fewer than 8 readings are flagged as sparse and excluded from trend
              calculations.
            </dd>
            <dt>WFD compliance</dt>
            <dd>
              A station-year is compliant if the annual mean P(SOL) is at or below 0.035 mg/l,
              the WFD "Good" status threshold for soluble reactive phosphorus. This is a chemical
              threshold only; full WFD classification also requires biological quality
              assessments.
            </dd>
            <dt>5-year rolling mean</dt>
            <dd>
              Centred on each year (plus or minus 2 years). Computed only where the full 5-year
              window is present and at least 3 of those years are non-sparse.
            </dd>
            <dt>Trend classification (Mann-Kendall)</dt>
            <dd>
              Applied to non-sparse annual means from 2010 onwards, using a minimum of 8
              qualifying years per station. The 2010 baseline separates the post-sewage-improvement
              era from the current monitoring period. Results are classified as increasing,
              decreasing, or no trend, with a significance flag at p &lt; 0.05 and Sen's slope as
              an effect size estimate.
            </dd>
            <dt>Cattle density</dt>
            <dd>
              NISRA cattle headcounts divided by area farmed (hectares), at ward level. Livestock
              units per hectare use standard conversion factors: cattle = 1.0, sheep = 0.15, pigs
              = 0.25.
            </dd>
            <dt>Below-detection readings</dt>
            <dd>
              Values below the instrument detection limit are halved and retained rather than
              discarded (half-detection-limit substitution, standard practice).
            </dd>
            <dt>Outlier handling</dt>
            <dd>
              Readings exceeding 20 times the station's all-time median are flagged in the
              database but are included in annual mean calculations.
            </dd>
          </dl>
        </section>

        <section className="methodology-section">
          <h2>What This Tool Cannot Tell You</h2>
          <div className="methodology-cannot">
            <div className="methodology-cannot-item">
              <h3>Whether agriculture causes the pollution</h3>
              <p>
                The spatial overlap between high cattle density and high phosphorus exceedance is
                visible. The tool cannot prove causation. The mechanisms (slurry storage,
                application, and runoff) are agronomically plausible, but correlation in this data
                is not causal evidence.
              </p>
            </div>
            <div className="methodology-cannot-item">
              <h3>The relative contribution of sewage versus agriculture</h3>
              <p>
                Both are phosphorus sources, and the tool now shows where each pressure sits — cattle
                density by ward, and NI Water storm overflows by asset. It still cannot disaggregate
                them at any station. Spill frequency and volume are not phosphorus load: without the
                concentration of what is discharged, volume alone cannot be converted into a share of
                the phosphorus in a river.
              </p>
              <p>
                The spill figures are also modelled rather than measured, and around half of NI
                Water's registered overflow assets have not been modelled at all. An asset drawn as a
                hollow ring is one with no published estimate — not one that never spills. Neither
                layer should be read as attribution.
              </p>
            </div>
            <div className="methodology-cannot-item">
              <h3>How much phosphorus enters the system</h3>
              <p>
                Concentration (mg/l) is measured, not load (kg/day). Without discharge volumes,
                total phosphorus cannot be calculated.
              </p>
            </div>
            <div className="methodology-cannot-item">
              <h3>Lough Neagh's historical status</h3>
              <p>
                WFD lake classifications are only available for 2024. The current "Bad"
                classification is shown, but its trajectory over time cannot be displayed.
              </p>
            </div>
            <div className="methodology-cannot-item">
              <h3>What is happening inside the lake</h3>
              <p>
                Sediment phosphorus release from the lakebed is a significant legacy source,
                independent of what rivers carry in. The tool shows river inputs only.
              </p>
            </div>
          </div>
        </section>

        <footer className="methodology-footer">
          <a href="/">← Back to map</a>
        </footer>
      </div>
    </div>
  )
}
