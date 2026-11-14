import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import { me, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const tokens = (a: string, r: string) => ({ user_id: "u-1", access_token: a, refresh_token: r, token_type: "bearer", expires_in: 900 });

function fillLogin(email: string, pw: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: pw } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("AuthProvider", () => {
  it("redirects to login when signed out, then signs in and lands on the page asked for", async () => {
    const api = mockApi({
      "POST /api/v1/auth/login": { body: tokens("at-9", "rt-9") },
      "GET /api/v1/me": (c) => (c.auth === "Bearer at-9" ? { body: me } : { status: 401, body: { error: "unauthorized", message: "x" } }),
      "GET /api/v1/today": { body: today },
    });
    render(<App initialPath="/" />);
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeTruthy();
    fillLogin("ada@example.invalid", "long enough password");
    expect(await screen.findByRole("heading", { name: "Today" })).toBeTruthy();
    expect(api.called("POST /api/v1/auth/login")[0].body).toEqual({ email: "ada@example.invalid", password: "long enough password" });
    expect(sessionStorage.getItem("ahm.access")).toBe("at-9");
  });

  it("Try the demo signs in, marks setup done and lands on Today", async () => {
    const api = mockApi({
      "POST /api/v1/auth/demo": { body: tokens("at-d", "rt-d") },
      "GET /api/v1/me": (c) => (c.auth === "Bearer at-d" ? { body: me } : { status: 401, body: { error: "unauthorized", message: "x" } }),
      "GET /api/v1/today": { body: today },
    });
    localStorage.removeItem("setup.done");
    render(<App initialPath="/login" />);
    fireEvent.click(await screen.findByRole("button", { name: "Try the demo" }));
    expect(await screen.findByRole("heading", { name: "Today" })).toBeTruthy();
    expect(api.called("POST /api/v1/auth/demo")).toHaveLength(1);
    expect(sessionStorage.getItem("ahm.access")).toBe("at-d");
    expect(localStorage.getItem("setup.done")).toBe("true");
    expect(localStorage.getItem("ahm.demo.refresh")).toBe("rt-d");
    localStorage.removeItem("ahm.demo.refresh");
  });

  it("Try the demo shows a loading state, then the full message on 503 demo_full", async () => {
    mockApi({ "POST /api/v1/auth/demo": { status: 503, body: { error: "demo_full", message: "demo is full" } } });
    render(<App initialPath="/login" />);
    fireEvent.click(await screen.findByRole("button", { name: "Try the demo" }));
    expect(screen.getByRole("button", { name: "Preparing your demo…" })).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("The demo is full right now."));
    expect(screen.getByRole("button", { name: "Try the demo" })).toBeTruthy();
  });

  it("a return demo visitor reuses the stored demo copy instead of making a new one", async () => {
    localStorage.setItem("ahm.demo.refresh", "rt-demo");
    const api = mockApi({
      "POST /api/v1/auth/refresh": { body: tokens("at-r", "rt-r") },
      "GET /api/v1/me": (c) => (c.auth === "Bearer at-r" ? { body: me } : { status: 401, body: { error: "unauthorized", message: "x" } }),
      "GET /api/v1/today": { body: today },
    });
    render(<App initialPath="/" />);
    expect(await screen.findByRole("heading", { name: "Today" })).toBeTruthy();
    expect(api.called("POST /api/v1/auth/demo")).toHaveLength(0);
    expect(localStorage.getItem("ahm.demo.refresh")).toBe("rt-r");
    localStorage.removeItem("ahm.demo.refresh");
  });

  it("a normal sign-in never keeps a token in localStorage", async () => {
    mockApi({
      "POST /api/v1/auth/login": { body: tokens("at-9", "rt-9") },
      "GET /api/v1/me": (c) => (c.auth === "Bearer at-9" ? { body: me } : { status: 401, body: { error: "unauthorized", message: "x" } }),
      "GET /api/v1/today": { body: today },
    });
    render(<App initialPath="/login" />);
    fillLogin("ada@example.invalid", "long enough password");
    expect(await screen.findByRole("heading", { name: "Today" })).toBeTruthy();
    expect(localStorage.getItem("ahm.demo.refresh")).toBeNull();
  });

  it("signup shows the closed message on 403 signup_closed", async () => {
    mockApi({ "POST /api/v1/auth/signup": { status: 403, body: { error: "signup_closed", message: "closed" } } });
    render(<App initialPath="/register" />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.invalid" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long enough password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Sign-ups are closed for this demo."));
  });

  it("hides Try the demo when the server has demo access off (404)", async () => {
    mockApi({ "POST /api/v1/auth/demo": { status: 404, body: { error: "not_found", message: "Not Found" } } });
    render(<App initialPath="/login" />);
    fireEvent.click(await screen.findByRole("button", { name: "Try the demo" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Try the demo" })).toBeNull());
    expect(screen.getByRole("alert").textContent).toBe("");
  });

  it("shows the throttling message with the Retry-After wait", async () => {
    mockApi({
      "POST /api/v1/auth/login": {
        status: 429,
        headers: { "Retry-After": "120" },
        body: { error: "too_many_attempts", message: "too many failed logins; try again later" },
      },
    });
    render(<App initialPath="/login" />);
    fillLogin("ada@example.invalid", "wrong password!!");
    expect((await screen.findByRole("alert")).textContent).toBe("Too many failed sign-ins. Try again in about 2 minutes.");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    signIn("expired", "rt-1");
    const api = mockApi({
      "POST /api/v1/auth/refresh": { body: tokens("at-2", "rt-2") },
      "GET /api/v1/me": (c) => (c.auth === "Bearer at-2" ? { body: me } : { status: 401, body: { error: "unauthorized", message: "x" } }),
      "GET /api/v1/today": (c) => (c.auth === "Bearer at-2" ? { body: today } : { status: 401, body: { error: "unauthorized", message: "x" } }),
    });
    render(<App initialPath="/" />);
    expect(await screen.findByRole("heading", { name: "Today" })).toBeTruthy();
    expect(api.called("POST /api/v1/auth/refresh")).toHaveLength(1); // one rotation shared
    expect(api.called("POST /api/v1/auth/refresh")[0].body).toEqual({ refresh_token: "rt-1" });
    expect(sessionStorage.getItem("ahm.refresh")).toBe("rt-2");
  });

  it("goes back to login and forgets the tokens when the refresh fails", async () => {
    signIn("expired", "revoked");
    mockApi({
      "POST /api/v1/auth/refresh": { status: 401, body: { error: "unauthorized", message: "invalid refresh token" } },
      "GET /api/v1/me": { status: 401, body: { error: "unauthorized", message: "x" } },
    });
    render(<App initialPath="/sleep" />);
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeTruthy();
    expect(sessionStorage.getItem("ahm.access")).toBeNull();
    expect(sessionStorage.getItem("ahm.refresh")).toBeNull();
  });

  it("logout revokes the refresh token and returns to login", async () => {
    signIn("at-1", "rt-1");
    const api = mockApi({
      "GET /api/v1/me": { body: me },
      "GET /api/v1/today": { body: today },
      "POST /api/v1/auth/logout": { status: 204 },
    });
    render(<App initialPath="/" />);
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeTruthy();
    await waitFor(() => expect(api.called("POST /api/v1/auth/logout")).toHaveLength(1));
    expect(api.called("POST /api/v1/auth/logout")[0].body).toEqual({ refresh_token: "rt-1" });
    expect(sessionStorage.getItem("ahm.refresh")).toBeNull();
  });
});
