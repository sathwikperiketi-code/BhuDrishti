import { AlertCircle, ArrowUpRight, Crosshair, FileSearch, Layers3 } from 'lucide-react'
import { confidencePercent, confidenceTone, fieldLabel, fieldValue, FIELD_ORDER } from './format'
import type { DocumentDetail, ExtractedField } from './types'

type Props = { document: DocumentDetail; selectedField: string | null; onFieldSelect: (field: string) => void; showValidationLink?: boolean }

function confidenceText(value: number | null) {
  const percent = confidencePercent(value)
  if (percent == null) return 'Unmeasured'
  return percent >= 85 ? 'High' : percent >= 60 ? 'Review' : 'Low'
}

function compareField(a: ExtractedField, b: ExtractedField) {
  const left = FIELD_ORDER.indexOf(a.field)
  const right = FIELD_ORDER.indexOf(b.field)
  return (left < 0 ? 100 : left) - (right < 0 ? 100 : right)
}

export function LiveExtractionPanel({ document, selectedField, onFieldSelect, showValidationLink = true }: Props) {
  const fields = [...document.fields].sort(compareField)
  const selected = fields.find((field) => field.field === selectedField)
  const withEvidence = fields.filter((field) => field.source?.bbox).length
  return (
    <section className="ldw-extraction-card" aria-labelledby="ldw-extraction-title">
      <div className="ldw-card-heading"><div><span className="ldw-eyebrow">Structured extraction</span><h2 id="ldw-extraction-title">Land record fields</h2></div><span className="ldw-card-aside">{fields.length} fields · {withEvidence} linked</span></div>
      {fields.length === 0 ? <div className="ldw-panel-empty"><Layers3 size={26} aria-hidden="true" /><strong>Awaiting extraction</strong><p>Fields appear here when the backend identifies values from this uploaded source. Start processing to begin.</p></div> : <div className="ldw-fields" aria-label="Extracted land record fields">
        {fields.map((field) => {
          const selected = selectedField === field.field
          const percent = confidencePercent(field.confidence)
          const tone = confidenceTone(field.confidence)
          const missing = field.value == null || field.value === ''
          return <button key={field.field} type="button" className={`ldw-field ${selected ? 'ldw-field--selected' : ''}`} aria-pressed={selected} onClick={() => onFieldSelect(field.field)}>
            <span className="ldw-field-main"><span className="ldw-field-label">{fieldLabel(field.field)}</span><strong key={fieldValue(field)} className={missing ? 'ldw-field-missing' : 'ldw-field-value'}>{fieldValue(field)}</strong><small className="ldw-field-source">{field.source?.page ? `Page ${field.source.page}` : 'Page unavailable'} · {field.source?.bbox ? 'Region linked' : field.source?.text ? 'Text evidence' : 'Evidence unavailable'}</small></span>
            <span className="ldw-field-side"><span className={`ldw-confidence ldw-confidence--${tone}`} aria-label={`${fieldLabel(field.field)} extraction confidence ${percent == null ? 'unmeasured' : `${percent} percent, ${confidenceText(field.confidence)}`}`}><b>{percent == null ? '—' : `${percent}%`}</b><small>{confidenceText(field.confidence)}</small></span>{field.source?.bbox ? <Crosshair size={14} aria-hidden="true" /> : <FileSearch size={14} aria-hidden="true" />}</span>
          </button>
        })}
      </div>}
      {selected ? <div className="ldw-evidence-detail" aria-live="polite"><div><span className="ldw-eyebrow">Source evidence</span><strong>{fieldLabel(selected.field)}</strong></div><p>{selected.source?.text ? `“${selected.source.text}”` : selected.source?.bbox ? 'Bounding box available on the original page.' : 'No source coordinates were provided for this field.'}</p><dl><div><dt>Page</dt><dd>{selected.source?.page ?? '—'}</dd></div><div><dt>Method</dt><dd>{selected.extractionMethod ?? 'Unspecified'}</dd></div><div><dt>Extraction confidence</dt><dd>{confidencePercent(selected.confidence) == null ? 'Unmeasured' : `${confidencePercent(selected.confidence)}%`}</dd></div></dl>{selected.warnings.length > 0 ? <div className="ldw-field-warnings"><AlertCircle size={14} aria-hidden="true" /><span>{selected.warnings.join(' · ')}</span></div> : null}</div> : null}
      <footer className="ldw-panel-foot"><span>Confidence supports review; it does not establish ownership.</span>{showValidationLink ? <a href={`#/validation?id=${encodeURIComponent(document.id)}`}>Validation <ArrowUpRight size={14} aria-hidden="true" /></a> : null}</footer>
    </section>
  )
}
