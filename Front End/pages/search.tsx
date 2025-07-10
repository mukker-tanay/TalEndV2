import { useState } from "react";
import CVSlider, { CVType } from "../components/CVSlider";
import Slider from "rc-slider";
import "rc-slider/assets/index.css";
import { FaFilter } from "react-icons/fa"; // 🔍 Funnel icon

type SearchResult = {
  _id: string;
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  current_company?: string;
  current_position?: string;
  last_education?: string;
  graduation_batch?: number;
  skills?: string[];
  match_score: number;
  stored_filename: string;
  original_filename: string;
  upload_time?: string;
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [sliderOpen, setSliderOpen] = useState(false);
  const [sliderIndex, setSliderIndex] = useState(0);
  const [showFilters, setShowFilters] = useState(false); // 🔁 Toggle for filters

  const currentYear = new Date().getFullYear();
  
  // Initialize batch range to full range (1950-2030) to avoid filtering when hidden
  const [batchMin, setBatchMin] = useState(1950);
  const [batchMax, setBatchMax] = useState(2030);
  const [lastEducation, setLastEducation] = useState("");
  const [uploadRange, setUploadRange] = useState<string>("");

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    if (!token) {
      console.error("No auth token found");
      setLoading(false);
      return;
    }

    const params = new URLSearchParams();
    params.append("query", query);
    
    // Only add filters if the filter section is visible AND values are meaningful
    if (showFilters) {
      // Only add batch filters if they're not at the full range
      if (batchMin > 1950) {
        params.append("batch_min", batchMin.toString());
      }
      if (batchMax < 2030) {
        params.append("batch_max", batchMax.toString());
      }
      
      // Only add education filter if it has a value
      if (lastEducation.trim()) {
        params.append("last_education", lastEducation.trim());
      }
      
      // Only add upload range if selected
      if (uploadRange.trim()) {
        params.append("upload_range", uploadRange.trim());
      }
    }

    try {
      const res = await fetch(`http://localhost:8000/search-cvs?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        const errMsg = await res.text();
        console.error("Backend error:", res.status, errMsg);
        setLoading(false);
        return;
      }

      const data = await res.json();
      console.log("Search response:", data); // Debug log
      setResults(Array.isArray(data.results) ? data.results : []);
    } catch (err) {
      console.error("Search error:", err);
    }

    setLoading(false);
  };

  const closePanel = () => {
    setSliderOpen(false);
  };

  const openSlider = (cv: SearchResult) => {
    const idx = results.findIndex((item) => item._id === cv._id);
    setSliderIndex(idx);
    setSliderOpen(true);
  };

  // Reset all filters
  const resetFilters = () => {
    setBatchMin(1950);
    setBatchMax(2030);
    setLastEducation("");
    setUploadRange("");
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow p-4 flex justify-between items-center sticky top-0 z-10">
        <div className="text-xl font-bold text-blue-600">Talend</div>
        <div className="space-x-4">
          <button onClick={() => (window.location.href = "/dashboard")} className="text-sm text-gray-700 hover:text-blue-600">Dashboard</button>
          <button onClick={() => (window.location.href = "/profile")} className="text-sm text-gray-700 hover:text-blue-600">Profile</button>
          <button onClick={() => { localStorage.removeItem("token"); window.location.href = "/login"; }} className="text-sm text-red-600 hover:underline">Logout</button>
        </div>
      </nav>

      <div className="px-6 py-10 max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">CV Search</h1>
        <p className="text-sm text-gray-500 mb-6">Sorted by best match score</p>

        <form onSubmit={handleSearch} className="flex flex-col gap-4 mb-8 bg-white p-4 rounded shadow">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search by keyword (e.g., React, Python, SQL, or person name)"
              className="flex-grow px-4 py-2 border rounded"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
              {loading ? "Searching..." : "Search"}
            </button>
          </div>

          {/* 🔁 Filter toggle */}
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">Search Filters</span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                className="text-blue-600 flex items-center gap-1 text-sm"
              >
                <FaFilter />
                {showFilters ? "Hide Filters" : "Show Filters"}
              </button>
              {showFilters && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="text-gray-500 text-xs underline"
                >
                  Reset All
                </button>
              )}
            </div>
          </div>

          {/* 📂 Filters section (collapsible) */}
          {showFilters && (
            <div className="flex flex-wrap gap-6 items-center mt-2 p-4 bg-gray-50 rounded">
              {/* Batch slider */}
              <div className="flex flex-col w-full max-w-md">
                <label className="text-xs font-semibold mb-1">Graduation Batch Year</label>
                <Slider
                  range
                  min={1950}
                  max={2030}
                  value={[batchMin, batchMax]}
                  onChange={(value: number | [number, number]) => {
                    if (Array.isArray(value)) {
                      const [min, max] = value;
                      setBatchMin(min);
                      setBatchMax(max);
                    }
                  }}
                  allowCross={false}
                  trackStyle={[{ backgroundColor: "#add8e6" }]}
                  handleStyle={[
                    { borderColor: "#808080", backgroundColor: "#808080" },
                    { borderColor: "#808080", backgroundColor: "#808080" },
                  ]}
                  railStyle={{ backgroundColor: "#e0e0e0" }}
                  style={{ width: "25rem", marginTop: "1rem" }}
                />
                <div className="flex justify-between text-xs mt-1 w-full" style={{ width: "25rem" }}>
                  <span>{batchMin}</span>
                  <span>{batchMax}</span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {batchMin === 1950 && batchMax === 2030 
                    ? "All years (no filter)" 
                    : `Filtering: ${batchMin} - ${batchMax}`}
                </div>
              </div>

              {/* Last education */}
              <div className="flex flex-col">
                <label className="text-xs font-semibold mb-1">Last Education</label>
                <input
                  type="text"
                  placeholder="e.g., B.Tech, MBA"
                  value={lastEducation}
                  onChange={(e) => setLastEducation(e.target.value)}
                  className="border rounded px-2 py-1"
                />
                <div className="text-xs text-gray-500 mt-1">
                  {lastEducation.trim() ? `Filter: ${lastEducation}` : "No filter"}
                </div>
              </div>

              {/* Upload date range */}
              <div className="flex flex-col">
                <label className="text-xs font-semibold mb-1">Uploaded</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {[
                    { label: "Within 1 month", value: "1m" },
                    { label: "Within 3 months", value: "3m" },
                    { label: "Within 6 months", value: "6m" },
                    { label: "Within 1 year", value: "1y" },
                    { label: "Within 2 years", value: "2y" },
                    { label: "2+ years ago", value: "2y+" },
                  ].map((opt) => (
                    <label key={opt.value} className="flex items-center gap-1 text-xs">
                      <input
                        type="radio"
                        name="uploadRange"
                        value={opt.value}
                        checked={uploadRange === opt.value}
                        onChange={() => setUploadRange(opt.value)}
                      />
                      {opt.label}
                    </label>
                  ))}
                  <button
                    type="button"
                    className="ml-2 text-xs text-gray-500 underline"
                    onClick={() => setUploadRange("")}
                    style={{ minWidth: 0 }}
                  >
                    Clear
                  </button>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {uploadRange ? `Filter: ${uploadRange}` : "No filter"}
                </div>
              </div>
            </div>
          )}

          {/* Show active filters summary */}
          {showFilters && (
            <div className="text-xs text-gray-600 bg-blue-50 p-2 rounded">
              <strong>Active Filters:</strong> {
                [
                  batchMin > 1950 || batchMax < 2030 ? `Batch: ${batchMin}-${batchMax}` : null,
                  lastEducation.trim() ? `Education: ${lastEducation}` : null,
                  uploadRange ? `Upload: ${uploadRange}` : null
                ].filter(Boolean).join(", ") || "None"
              }
            </div>
          )}
        </form>

        {/* 🔎 Results */}
        {results.length === 0 && !loading && query && (
          <p className="text-gray-500 text-sm">❌ No matches found for "{query}".</p>
        )}
        {results.length === 0 && !loading && !query && (
          <p className="text-gray-500 text-sm">Start by entering a search query.</p>
        )}

        <div className="grid gap-6">
          {results.map((cv) => (
            <div key={cv._id} className="cv-card relative">
              <div className="cv-badge">{cv.match_score.toFixed(2)}</div>
              <div className="mb-2">
                <h2 className="cv-name">{cv.name || "Unknown"}</h2>
                <p className="cv-meta">
                  {cv.email || "N/A"} | {cv.phone || "N/A"}
                </p>
              </div>
              <div className="cv-info-grid">
                <div><strong>Current Employer:</strong> {cv.current_company || "N/A"}</div>
                <div><strong>Designation:</strong> {cv.current_position || "N/A"}</div>
                <div><strong>Education:</strong> {cv.last_education}</div>
                <div><strong>Batch:</strong> {cv.graduation_batch || "N/A"}</div>
              </div>
              {cv.skills && cv.skills.length > 0 && (
                <div className="mt-2">
                  <strong>Skills:</strong>
                  <div className="flex flex-wrap mt-1">
                    {cv.skills.map((skill, idx) => (
                      <span key={idx} className="cv-skill-pill">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-4">
                <button onClick={() => openSlider(cv)} className="text-blue-600 text-sm underline">
                  View CV
                </button>
              </div>
              {cv.upload_time && (
                <div className="absolute bottom-2 right-4 text-xs text-gray-500">
                  Uploaded: {new Date(cv.upload_time).toLocaleDateString()}{" "}
                  {new Date(cv.upload_time).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {sliderOpen && (
        <CVSlider
          cvList={results as CVType[]}
          current={sliderIndex}
          setCurrent={setSliderIndex}
          onClose={closePanel}
        />
      )}
    </div>
  );
}