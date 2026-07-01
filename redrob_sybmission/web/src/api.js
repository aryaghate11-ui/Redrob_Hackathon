export async function getStatus() {
  const response = await fetch("/api/status");
  if (!response.ok) throw new Error("Unable to load model status");
  return response.json();
}

export async function getCandidates(filters = {}) {
  const params = new URLSearchParams({
    limit: "250",
    search: filters.search || "",
    tier: filters.tier || "all",
    availability: filters.availability || "all",
    model: filters.model || "workdna",
  });
  const response = await fetch(`/api/candidates?${params}`);
  if (!response.ok) throw new Error("Unable to load ranked candidates");
  return response.json();
}

export async function importDataset(file, onProgress) {
  const response = await fetch(
    `/api/import?filename=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
      },
      body: file,
    },
  );
  onProgress?.(100);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Import failed");
  return payload;
}

export function exportUrl(topK = 100, model = "workdna") {
  return `/api/export?top_k=${topK}&model=${model}`;
}
