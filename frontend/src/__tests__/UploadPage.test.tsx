import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { UploadPage } from "../pages/UploadPage";

describe("UploadPage", () => {
  it("displays format requirements and validates oversized files client-side", async () => {
    render(
      <BrowserRouter>
        <UploadPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/Upload Workload CSV/i)).toBeInTheDocument();
    expect(screen.getByText(/Expected CSV Format/i)).toBeInTheDocument();
    expect(screen.getByText(/service_id,timestamp,cpu_demand/i)).toBeInTheDocument();

    // Create an oversized 6 MB file
    const oversizedContent = new Uint8Array(6 * 1024 * 1024);
    const oversizedFile = new File([oversizedContent], "large.csv", {
      type: "text/csv",
    });

    const dropZone = screen.getByText(/Choose CSV or drag and drop here/i);
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [oversizedFile] },
    });

    await waitFor(() => {
      expect(
        screen.getByText(/exceeds maximum allowed limit of 5.0 MB/i)
      ).toBeInTheDocument();
    });
  });
});
