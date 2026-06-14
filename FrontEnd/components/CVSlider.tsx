import React, { useEffect, useState } from "react";

let API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
if (typeof window !== "undefined" && window.location.hostname === "jobnoc.com") {
  API_URL = "https://jobnoc.com/api";
}

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
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState(false);
  const [docHtml, setDocHtml] = useState<string | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState(false);

  const cv = cvList[current];
  const storedFilename = cv?.stored_filename ?? "";
  const isPDF = storedFilename.toLowerCase().endsWith(".pdf");
  const isDOC = /\.(docx?)$/i.test(storedFilename);
  const previewUrl = isPDF
    ? `${API_URL}/cv/preview/${encodeURIComponent(storedFilename)}`
    : "";
  const downloadUrl = `${API_URL}/cv/download/${encodeURIComponent(storedFilename)}`;

  useEffect(() => {
    if (!isPDF || !storedFilename) {
      setPdfBlobUrl(null);
      setPdfLoading(false);
      setPdfError(false);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;

    setPdfLoading(true);
    setPdfError(false);
    setPdfBlobUrl(null);

    fetch(previewUrl)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load PDF");
        return res.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPdfBlobUrl(objectUrl);
        setPdfLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setPdfError(true);
          setPdfLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [storedFilename, isPDF, previewUrl]);

  useEffect(() => {
    if (!isDOC || !storedFilename) {
      setDocHtml(null);
      setDocLoading(false);
      setDocError(false);
      return;
    }

    let cancelled = false;
    setDocLoading(true);
    setDocError(false);
    setDocHtml(null);

    fetch(downloadUrl)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch DOCX");
        return res.arrayBuffer();
      })
      .then((buffer) => {
        if (cancelled) return;
        return import("mammoth").then((mammoth) =>
          mammoth.convertToHtml({ arrayBuffer: buffer })
        );
      })
      .then((result) => {
        if (cancelled || !result) return;
        setDocHtml(result.value);
        setDocLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setDocError(true);
          setDocLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [storedFilename, isDOC, downloadUrl]);

  if (!cvList.length || !cv) return null;

  const goPrev = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrent(current > 0 ? current - 1 : current);
  };

  const goNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrent(current < cvList.length - 1 ? current + 1 : current);
  };

  return (
    <div className="fixed inset-0 bg-gray-900/40 backdrop-blur-sm z-40 flex justify-end" onClick={onClose}>
      <div
        className="h-full bg-gray-50 border-l border-gray-200 shadow-xl flex flex-col z-50 animate-slide-in-right"
        style={{ width: "45vw", maxWidth: 750, minWidth: 350 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-gray-200 bg-white">
          <div className="max-w-[70%]">
            <h3 className="text-md font-bold text-gray-900 truncate" title={cv.original_filename}>
              {cv.name || cv.original_filename}
            </h3>
            <p className="text-[10px] text-gray-500 truncate font-semibold uppercase tracking-wider mt-0.5">{cv.original_filename}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-900 text-xl font-bold bg-gray-100 hover:bg-gray-200 px-2.5 py-0.5 rounded-lg transition-all"
            aria-label="Close"
          >
            x
          </button>
        </div>

        {/* PDF Preview Frame */}
        <div className="flex-1 min-h-0 overflow-hidden p-6 flex flex-col bg-gray-100/50">
          {isPDF ? (
            pdfLoading ? (
              <div className="flex-1 flex items-center justify-center text-sm text-gray-500 font-semibold">
                Loading PDF preview...
              </div>
            ) : pdfError ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-white border border-gray-200 rounded-xl max-w-sm mx-auto">
                <p className="text-sm text-red-500 font-semibold mb-2">Could not load PDF preview.</p>
                <p className="text-xs text-gray-500">
                  The file may be missing from the server. Try downloading it instead.
                </p>
              </div>
            ) : pdfBlobUrl ? (
              <iframe
                src={pdfBlobUrl}
                title={`Preview of ${cv.original_filename}`}
                className="flex-1 w-full min-h-0 rounded-xl border border-gray-200 bg-white shadow-sm"
              />
            ) : null
          ) : isDOC ? (
            docLoading ? (
              <div className="flex-1 flex items-center justify-center text-sm text-gray-500 font-semibold">
                Loading document preview...
              </div>
            ) : docError ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-white border border-gray-200 rounded-xl max-w-sm mx-auto">
                <p className="text-sm text-red-500 font-semibold mb-2">Could not load document preview.</p>
                <p className="text-xs text-gray-500">Try downloading the file instead.</p>
              </div>
            ) : docHtml ? (
              <div
                className="flex-1 w-full min-h-0 overflow-y-auto rounded-xl border border-gray-200 bg-white shadow-sm p-6 prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: docHtml }}
              />
            ) : null
          ) : (
            <div className="text-center p-8 bg-white border border-gray-200 rounded-xl max-w-sm">
              <p className="text-sm text-red-400 font-semibold">Unsupported resume file format.</p>
            </div>
          )}
        </div>

        {/* Dynamic Outreach Toolbar */}
        {(cv.email || cv.phone) && (
          <div className="px-6 py-3 border-t border-gray-200 bg-white flex items-center gap-2">
            {cv.email && (
              <a
                href={`mailto:${cv.email}`}
                className="flex-1 text-center py-2 rounded-xl bg-gray-900 hover:bg-black text-white text-xs font-semibold shadow-sm transition-all"
              >
                Send Email
              </a>
            )}
            {cv.phone && (
              <a
                href={`https://wa.me/${cv.phone.replace(/[^\d]/g, "")}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 text-center py-2 rounded-xl bg-green-600 hover:bg-green-700 text-white text-xs font-semibold shadow-sm transition-all"
              >
                WhatsApp Chat
              </a>
            )}
          </div>
        )}

        {/* Navigation Bar */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-gray-200 bg-gray-50">
          <button
            onClick={goPrev}
            disabled={current === 0}
            className="px-3.5 py-1.5 rounded-lg bg-white border border-gray-300 hover:bg-gray-100 text-gray-700 text-xs font-semibold disabled:opacity-30 disabled:hover:bg-white transition-all"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500 font-bold uppercase tracking-wider">
            {current + 1} of {cvList.length}
          </span>
          <button
            onClick={goNext}
            disabled={current === cvList.length - 1}
            className="px-3.5 py-1.5 rounded-lg bg-white border border-gray-300 hover:bg-gray-100 text-gray-700 text-xs font-semibold disabled:opacity-30 disabled:hover:bg-white transition-all"
          >
            Next
          </button>
        </div>

        <div className="p-6 border-t border-gray-200 bg-white">
          <a
            href={`${API_URL}/cv/download/${encodeURIComponent(cv.stored_filename)}`}
            target="_blank"
            rel="noopener noreferrer"
            download
            className="block"
          >
            <button className="bg-white hover:bg-gray-50 text-gray-900 border border-gray-300 py-2.5 rounded-xl font-semibold w-full transition-all text-xs">
              Download Original CV File
            </button>
          </a>
        </div>
      </div>
    </div>
  );
};

export default CVSlider;

