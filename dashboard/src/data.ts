import { verifyBytes } from './integrity';
export { verifyBytes } from './integrity';
export { SupabaseExperimentRepository } from './supabase';
import { assertVersion, decodeVoltage, validateExperiment, validateGraph } from './telemetry';
import type { Catalog, CatalogEntry, Graph, LoadedExperiment } from './telemetry';

/** Implement the same contract for a PostgreSQL catalog and Supabase Storage later.
 * No browser simulator and no service secrets. HTTP assets can already live at a
 * public static/Storage base URL; signed-URL authorization belongs to a future adapter. */
export interface TelemetrySource {
  getCatalog(): Promise<Catalog>;
  getGraph(catalog: Catalog): Promise<Graph>;
  getExperiment(entry: CatalogEntry, graph: Graph, graphHash: string): Promise<LoadedExperiment>;
}
export class HttpTelemetrySource implements TelemetrySource {
  constructor(private baseUrl: string, private fetcher: typeof fetch = (...args) => fetch(...args)) {}
  private async bytes(path: string, checksum?: string) {
    if (!/^[a-z0-9.-]+$/i.test(path)) throw new Error('Invalid telemetry asset path');
    const response = await this.fetcher(`${this.baseUrl.replace(/\/$/, '')}/${path}`);
    if (!response.ok) throw new Error(`Cannot load ${path}: HTTP ${response.status}`);
    const result = await response.arrayBuffer();
    if (checksum) await verifyBytes(result, checksum);
    return result;
  }
  async getCatalog() {
    const c = JSON.parse(new TextDecoder().decode(await this.bytes('catalog.json'))) as Catalog;
    assertVersion(c);
    if (c.biological_response_validated !== false || c.experiments.length !== 3 || !['baseline', 'weak', 'strong'].every(id => c.experiments.some(e => e.id === id))) throw new Error('Unsupported experiment catalog');
    return c;
  }
  async getGraph(catalog: Catalog) { return validateGraph(JSON.parse(new TextDecoder().decode(await this.bytes(catalog.graph.path, catalog.graph.sha256)))); }
  async getExperiment(entry: CatalogEntry, graph: Graph, graphHash: string) {
    const e = validateExperiment(JSON.parse(new TextDecoder().decode(await this.bytes(entry.path, entry.sha256))), graph, graphHash);
    if (e.id !== entry.id || e.spikes.length !== entry.spikes) throw new Error('Catalog experiment mismatch');
    return decodeVoltage(e, await this.bytes(e.voltage.path, e.voltage.sha256), graph);
  }
}
export const dataSource: TelemetrySource = new HttpTelemetrySource(import.meta.env.VITE_TELEMETRY_BASE_URL || `${import.meta.env.BASE_URL}data`);
