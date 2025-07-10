import React, { useState, useEffect } from "react";

export type CVType = {
  _id: string;
  original_filename: string;
  stored_filename: string;
  name?: string;
  current_position?: string;
  total_experience_years?: number;
  skills?: string[];
  match_score?: number;
  
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
    ? `http://localhost:8000/cv/preview/${cv.stored_filename}`
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
    <div className="fixed inset-0 bg-black bg-opacity-50 z-40 flex justify-end" onClick={onClose}>
      <div
        className="h-full bg-white shadow-lg border-l border-gray-300 flex flex-col z-50 animate-slide-in-right"
        style={{ width: "40vw", maxWidth: 700, minWidth: 320 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center px-4 py-3 border-b">
          <h3 className="text-lg font-semibold truncate max-w-xs" title={cv.original_filename}>
            {cv.original_filename}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-600 hover:text-black text-xl font-bold"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4 flex flex-col items-center justify-center">
          {isPDF ? (
            <embed
              src={embedUrl}
              type="application/pdf"
              width="100%"
              height="600px"
              className="rounded border"
            />
          ) : isDOC ? (
            <p className="text-sm text-gray-600 text-center">
              Preview not available for DOC/DOCX files.
              <br />
              You can download and open it locally.
            </p>
          ) : (
            <p className="text-sm text-red-500">Unsupported file type.</p>
          )}
        </div>

        <div className="flex items-center justify-between px-4 py-2 border-t bg-gray-50">
          <button
            onClick={goPrev}
            disabled={current === 0}
            className="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 disabled:opacity-50"
          >
            ◀ Prev
          </button>
          <span className="text-sm text-gray-500">
            {current + 1} / {cvList.length}
          </span>
          <button
            onClick={goNext}
            disabled={current === cvList.length - 1}
            className="px-3 py-1 rounded bg-gray-200 hover:bg-gray-300 disabled:opacity-50"
          >
            Next ▶
          </button>
        </div>

        <div className="p-4 border-t bg-white">
          <a
            href={`http://localhost:8000/cv/download/${cv.stored_filename}`}
            target="_blank"
            rel="noopener noreferrer"
            download
          >
            <button className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 w-full">
              ⬇ Download CV
            </button>
          </a>
        </div>
      </div>
    </div>
  );
};

export default CVSlider;
