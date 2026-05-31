import React from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type CVType = {
  _id: string;
  original_filename: string;
  stored_filename: string;
  name?: string;
  current_position?: string;
  total_experience_years?: number;
  skills?: string[];
  match_score?: number;
  email?: string;
  phone?: string;
};

type CVSliderProps = {
  cvList: CVType[];
  current: number;
  setCurrent: (idx: number) => void;
  onClose: () => void;
};

const CVSlider: React.FC<CVSliderProps> = ({ cvList, current, setCurrent, onClose }) => {
  if (!cvList.length) return null;

  const cv = cvList[current];
  const isPDF = cv?.stored_filename?.toLowerCase().endsWith(".pdf");
  const isDOC = /\.(docx?|rtf)$/i.test(cv?.stored_filename || "");
  const embedUrl = isPDF
    ? `${API_URL}/cv/preview/${cv.stored_filename}`
    : "";

  const goPrev = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrent(current > 0 ? current - 1 : current);
  };

  const goNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrent(current < cvList.length - 1 ? current + 1 : current);
  };

  return (
    <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm z-40 flex justify-end" onClick={onClose}>
      <div
        className="h-full bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col z-50 animate-slide-in-right"
        style={{ width: "45vw", maxWidth: 750, minWidth: 350 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-slate-800 bg-slate-950/20">
          <div className="max-w-[70%]">
            <h3 className="text-md font-bold text-slate-100 truncate" title={cv.original_filename}>
              {cv.name || cv.original_filename}
            </h3>
            <p className="text-[10px] text-slate-500 truncate font-semibold uppercase tracking-wider mt-0.5">{cv.original_filename}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-100 text-xl font-bold bg-slate-800 hover:bg-slate-750 px-2.5 py-0.5 rounded-lg transition-all"
            aria-label="Close"
          >
            x
          </button>
        </div>

        {/* PDF Preview Frame */}
        <div className="flex-1 overflow-auto p-6 flex flex-col items-center justify-center bg-slate-950/40">
          {isPDF ? (
            <embed
              src={embedUrl}
              type="application/pdf"
              width="100%"
              height="100%"
              className="rounded-xl border border-slate-800 bg-slate-950 shadow-inner"
            />
          ) : isDOC ? (
            <div className="text-center p-8 bg-slate-900 border border-slate-800 rounded-xl max-w-sm">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Preview Restricted</p>
              <p className="text-sm text-slate-300">
                Document preview is not supported for DOC/DOCX files.
              </p>
              <p className="text-xs text-slate-500 mt-2">
                Download the resume to view details offline.
              </p>
            </div>
          ) : (
            <div className="text-center p-8 bg-slate-900 border border-slate-800 rounded-xl max-w-sm">
              <p className="text-sm text-red-400 font-semibold">Unsupported resume file format.</p>
            </div>
          )}
        </div>

        {/* Dynamic Outreach Toolbar */}
        {(cv.email || cv.phone) && (
          <div className="px-6 py-3 border-t border-slate-850 bg-slate-950/30 flex items-center gap-2">
            {cv.email && (
              <a
                href={`mailto:${cv.email}`}
                className="flex-1 text-center py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/10 transition-all"
              >
                Send Email
              </a>
            )}
            {cv.phone && (
              <a
                href={`https://wa.me/${cv.phone.replace(/[^\d]/g, "")}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 text-center py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/10 transition-all"
              >
                WhatsApp Chat
              </a>
            )}
          </div>
        )}

        {/* Navigation Bar */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-slate-850 bg-slate-950/10">
          <button
            onClick={goPrev}
            disabled={current === 0}
            className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-200 text-xs font-semibold disabled:opacity-30 disabled:hover:bg-slate-800 transition-all"
          >
            Previous
          </button>
          <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">
            {current + 1} of {cvList.length}
          </span>
          <button
            onClick={goNext}
            disabled={current === cvList.length - 1}
            className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-200 text-xs font-semibold disabled:opacity-30 disabled:hover:bg-slate-800 transition-all"
          >
            Next
          </button>
        </div>

        {/* Download Footer */}
        <div className="p-6 border-t border-slate-850 bg-slate-900">
          <a
            href={`${API_URL}/cv/download/${cv.stored_filename}`}
            target="_blank"
            rel="noopener noreferrer"
            download
            className="block"
          >
            <button className="bg-slate-850 hover:bg-slate-800 text-slate-200 border border-slate-800 hover:border-slate-700 py-2.5 rounded-xl font-semibold w-full transition-all text-xs">
              Download Original CV File
            </button>
          </a>
        </div>
      </div>
    </div>
  );
};

export default CVSlider;

