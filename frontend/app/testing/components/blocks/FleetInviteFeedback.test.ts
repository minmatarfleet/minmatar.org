import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { expect, test } from "vitest";
import FleetInviteFeedback from "@components/blocks/FleetInviteFeedback.astro";
import type { InviteFeedbackForm } from "@helpers/fleet_invite_feedback";

const answers = {
  felt: "",
  sitting_out: "",
  why: "",
  why_text: "",
  improve: [],
  comment: "",
};

function form(invites: InviteFeedbackForm["invites"]): InviteFeedbackForm {
  return {
    state: "form",
    heading: "",
    body: "",
    detail: "",
    intro: "Counts go to fleet leadership. Your name is not on the results.",
    list_heading: "Your invites, last few weeks.",
    invites,
    pending_invites: [],
    questions: [
      {
        key: "felt",
        prompt: "Most of the time, these invites felt...",
        help: "",
        kind: "single",
        badge: "Required",
        exclusive: "",
        max: 1,
        choices: [
          { key: "fine", label: "Fine" },
          {
            key: "lighter",
            label: 'A "not this time" that doesn\'t feel like a no',
          },
        ],
      },
    ],
    answers,
    comment_heading: "One thing to change",
    comment_placeholder: "Optional. A sentence is enough.",
    errors: [],
  };
}

const props = {
  errors: [],
  attempted: null,
  partial_url: "/partials/fleet_invite_feedback_component/",
  edit_href: "/fleets/invite-feedback/?edit=1",
};

test("an empty invite list does not render the heading", async () => {
  const container = await AstroContainer.create();
  const html = await container.renderToString(FleetInviteFeedback, {
    props: { ...props, form: form([]) },
  });
  expect(html).not.toContain("Your invites, last few weeks.");
  expect(html).toContain('class="[ form ]"');
  expect(html).toContain("One thing to change");
});

test("invite rows keep the when, title, and answer together", async () => {
  const container = await AstroContainer.create();
  const html = await container.renderToString(FleetInviteFeedback, {
    props: {
      ...props,
      form: form([
        {
          fleet_id: 1,
          when: "Sun 18:00",
          title: "Sunday roam",
          answer: "pending",
          answer_label: "No answer",
        },
      ]),
    },
  });
  expect(html).toContain("Your invites, last few weeks.");
  expect(html).toContain("Sun 18:00");
  expect(html).toContain("Sunday roam");
  expect(html).toContain("No answer");
});
