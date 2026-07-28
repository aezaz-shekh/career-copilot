import {
  Button,
  Field,
  TextArea,
  arrayToLines,
  commasToArray,
  linesToArray,
} from './ui.jsx'

/**
 * Editable view of the parsed resume sections.
 *
 * This is the manual-fix step the SOW makes mandatory (§11): PDF layouts vary
 * enormously and a 3B model is not infallible, so nothing is saved or fed
 * downstream until the user has seen and corrected it. Every field is editable
 * and every list item can be added or removed.
 */

function ListSection({ title, items, onChange, blank, renderItem, addLabel }) {
  const update = (index, patch) =>
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)))

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">
          {title} <span className="text-sm font-normal text-slate-400">({items.length})</span>
        </h3>
        <Button variant="secondary" onClick={() => onChange([...items, { ...blank }])}>
          {addLabel}
        </Button>
      </div>

      {items.length === 0 && (
        <p className="mt-2 text-sm text-slate-400">
          Nothing detected. Add an entry if the parser missed one.
        </p>
      )}

      <div className="mt-3 space-y-4">
        {items.map((item, index) => (
          <div key={index} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            {renderItem(item, (patch) => update(index, patch))}
            <div className="mt-3 text-right">
              <Button
                variant="danger"
                onClick={() => onChange(items.filter((_, i) => i !== index))}
              >
                Remove
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ResumeEditor({ parsed, onChange }) {
  const set = (patch) => onChange({ ...parsed, ...patch })
  const setContact = (patch) => set({ contact: { ...parsed.contact, ...patch } })

  return (
    <div>
      <h3 className="font-semibold text-slate-900">Contact</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Field label="Name" value={parsed.contact?.name} onChange={(v) => setContact({ name: v })} />
        <Field
          label="Email"
          value={parsed.contact?.email}
          onChange={(v) => setContact({ email: v })}
        />
        <Field
          label="Phone"
          value={parsed.contact?.phone}
          onChange={(v) => setContact({ phone: v })}
        />
        <Field
          label="Location"
          value={parsed.contact?.location}
          onChange={(v) => setContact({ location: v })}
        />
      </div>
      <div className="mt-3">
        <TextArea
          label="Links (one per line)"
          rows={2}
          value={arrayToLines(parsed.contact?.links)}
          onChange={(v) => setContact({ links: linesToArray(v) })}
        />
      </div>

      <div className="mt-6">
        <TextArea
          label="Summary"
          rows={3}
          value={parsed.summary}
          onChange={(v) => set({ summary: v || null })}
          placeholder="No summary found in the resume."
        />
      </div>

      <div className="mt-6">
        <TextArea
          label="Skills (comma separated)"
          rows={3}
          value={(parsed.skills ?? []).join(', ')}
          onChange={(v) => set({ skills: commasToArray(v) })}
        />
        <p className="mt-1 text-xs text-slate-400">{(parsed.skills ?? []).length} skills detected</p>
      </div>

      <ListSection
        title="Experience"
        addLabel="Add role"
        items={parsed.experience ?? []}
        onChange={(v) => set({ experience: v })}
        blank={{ role: '', company: null, location: null, start_date: null, end_date: null, bullets: [] }}
        renderItem={(item, patch) => (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Role" value={item.role} onChange={(v) => patch({ role: v ?? '' })} />
              <Field label="Company" value={item.company} onChange={(v) => patch({ company: v })} />
              <Field
                label="Start"
                value={item.start_date}
                onChange={(v) => patch({ start_date: v })}
              />
              <Field label="End" value={item.end_date} onChange={(v) => patch({ end_date: v })} />
            </div>
            <div className="mt-3">
              <TextArea
                label="Bullets (one per line)"
                rows={4}
                value={arrayToLines(item.bullets)}
                onChange={(v) => patch({ bullets: linesToArray(v) })}
              />
            </div>
          </>
        )}
      />

      <ListSection
        title="Education"
        addLabel="Add qualification"
        items={parsed.education ?? []}
        onChange={(v) => set({ education: v })}
        blank={{ degree: '', institution: null, start_date: null, end_date: null, details: null }}
        renderItem={(item, patch) => (
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Degree" value={item.degree} onChange={(v) => patch({ degree: v ?? '' })} />
            <Field
              label="Institution"
              value={item.institution}
              onChange={(v) => patch({ institution: v })}
            />
            <Field
              label="Start"
              value={item.start_date}
              onChange={(v) => patch({ start_date: v })}
            />
            <Field label="End" value={item.end_date} onChange={(v) => patch({ end_date: v })} />
            <div className="sm:col-span-2">
              <Field
                label="Details (CGPA, coursework)"
                value={item.details}
                onChange={(v) => patch({ details: v })}
              />
            </div>
          </div>
        )}
      />

      <ListSection
        title="Projects"
        addLabel="Add project"
        items={parsed.projects ?? []}
        onChange={(v) => set({ projects: v })}
        blank={{ name: '', description: null, bullets: [], technologies: [] }}
        renderItem={(item, patch) => (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Name" value={item.name} onChange={(v) => patch({ name: v ?? '' })} />
              <Field
                label="Technologies (comma separated)"
                value={(item.technologies ?? []).join(', ')}
                onChange={(v) => patch({ technologies: commasToArray(v ?? '') })}
              />
            </div>
            <div className="mt-3">
              <Field
                label="Description"
                value={item.description}
                onChange={(v) => patch({ description: v })}
              />
            </div>
            <div className="mt-3">
              <TextArea
                label="Bullets (one per line)"
                rows={3}
                value={arrayToLines(item.bullets)}
                onChange={(v) => patch({ bullets: linesToArray(v) })}
              />
            </div>
          </>
        )}
      />

      <div className="mt-6">
        <TextArea
          label="Certifications (one per line)"
          rows={3}
          value={arrayToLines(parsed.certifications)}
          onChange={(v) => set({ certifications: linesToArray(v) })}
        />
      </div>
    </div>
  )
}
