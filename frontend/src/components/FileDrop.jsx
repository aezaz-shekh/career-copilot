import { useRef, useState } from 'react'

/** Drag-and-drop file picker that also works as a plain click-to-browse button. */
export default function FileDrop({ onFile, disabled, accept = '.pdf,.txt' }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  function handleDrop(event) {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    const file = event.dataTransfer.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
      }}
      className={[
        'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-10 text-center transition',
        dragging ? 'border-slate-900 bg-slate-100' : 'border-slate-300 bg-slate-50 hover:bg-slate-100',
        disabled ? 'cursor-not-allowed opacity-50' : '',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onFile(file)
          e.target.value = '' // allow re-picking the same file
        }}
      />
      <p className="font-medium text-slate-800">Drop your resume here, or click to browse</p>
      <p className="mt-1 text-sm text-slate-500">PDF or TXT, up to 5 MB</p>
      <p className="mt-3 text-xs text-slate-400">
        The file is read on this machine and never uploaded anywhere.
      </p>
    </div>
  )
}
