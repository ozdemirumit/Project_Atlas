import "@testing-library/jest-dom/vitest";

import { configure } from "@testing-library/react";
import { beforeEach } from "vitest";

configure({ asyncUtilTimeout: 3_000 });

beforeEach(() => {
  window.history.replaceState(null, "", "#/health");
});
