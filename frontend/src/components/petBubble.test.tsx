import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import { me, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";
import { toPetBubble } from "./CompanionHost";

const base = { voice: "warm", disclaimer: null, ui_action: null };
const BUBBLE = { ...base, id: "steady_night", badge: "green", playful: true, pet_animation: "curious_tilt", bubble: "Night after night, a gentle rhythm.", micro_try: "Try a slow breath before bed." };

function setup(bubble: Record<string, unknown>) {
  signIn();
  return mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: today },
    "GET /api/v1/nights": { body: [] },
    "GET /api/v1/pet/bubble": { body: bubble },
  });
}

describe("pet speech bubble from the server", () => {
  beforeEach(() => { localStorage.setItem("pet.firstRunDone", "true"); localStorage.setItem("pet.tip.switchCompanion", "1"); });

  it("shows one bubble with its try line, dismissible", async () => {
    setup(BUBBLE);
    render(<App initialPath="/" />);
    expect(await screen.findByText(BUBBLE.bubble)).toBeTruthy();
    expect(screen.getByText(BUBBLE.micro_try)).toBeTruthy();
    expect(document.querySelectorAll(".pet-bubble[data-show]")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() => expect(document.querySelector(".pet-bubble[data-show]")).toBeNull());
  });

  it("opens the existing safety screen on HALT_AND_OPEN_CRISIS_SCREEN, with no bubble", async () => {
    setup({ ...base, id: "safety_phq9_item9", badge: "crisis", playful: false, pet_animation: "calm_present", bubble: "Let's pause.", micro_try: null, ui_action: "HALT_AND_OPEN_CRISIS_SCREEN" });
    render(<App initialPath="/" />);
    expect(await screen.findByRole("alertdialog")).toBeTruthy();
    expect(screen.queryByText("Let's pause.")).toBeNull();
  });

  it("maps animations and badges (never red) and keeps calm bubbles calm", () => {
    expect(toPetBubble({ ...BUBBLE })).toMatchObject({ animation: "tilt", badge: "green", playful: true });
    expect(toPetBubble({ ...BUBBLE, pet_animation: "cozy_support", badge: "support", playful: false })).toMatchObject({ animation: "cozy", badge: "neutral", playful: false });
    expect(toPetBubble({ ...BUBBLE, badge: "red" })!.badge).toBe("neutral");
    expect(toPetBubble({ ...BUBBLE, bubble: null })).toBeNull();
  });

  it("playful:false puts the pet in calm idle", async () => {
    setup({ ...BUBBLE, playful: false, pet_animation: "cozy_glow" });
    render(<App initialPath="/" />);
    await screen.findByText(BUBBLE.bubble);
    const pet = document.querySelector(".pet")!;
    expect(pet.getAttribute("data-calm")).toBe("true");
    expect(pet.getAttribute("data-anim")).toBe("cozy");
  });

  it("a demo visitor's first visit to Today gets one tip about switching companions, after the server bubble", async () => {
    localStorage.removeItem("pet.tip.switchCompanion");
    setup(BUBBLE);
    const { unmount } = render(<App initialPath="/" />);
    expect(await screen.findByText(BUBBLE.bubble)).toBeTruthy();
    expect(screen.queryByText("You can switch companions in Settings.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(await screen.findByText("You can switch companions in Settings.")).toBeTruthy();
    expect(localStorage.getItem("pet.tip.switchCompanion")).toBe("1");
    unmount();
    setup({ ...BUBBLE, bubble: null });
    render(<App initialPath="/" />);
    await screen.findByRole("heading", { name: "Today" });
    await new Promise((r) => setTimeout(r, 300));
    expect(screen.queryByText("You can switch companions in Settings.")).toBeNull();
  });

  it("no tip for a real (non-demo) account", async () => {
    localStorage.removeItem("pet.tip.switchCompanion");
    signIn();
    mockApi({ "GET /api/v1/me": { body: { ...me, is_synthetic: false } }, "GET /api/v1/today": { body: today }, "GET /api/v1/nights": { body: [] }, "GET /api/v1/pet/bubble": { body: { ...BUBBLE, bubble: null } } });
    render(<App initialPath="/" />);
    await screen.findByRole("heading", { name: "Today" });
    await new Promise((r) => setTimeout(r, 300));
    expect(screen.queryByText("You can switch companions in Settings.")).toBeNull();
  });
});
