import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Typed client for the backend, generated from /openapi.json (`npm run gen:api`).
// Same origin: the API serves this app, so baseUrl is empty.
export const api = createClient<paths>({ baseUrl: "" });
