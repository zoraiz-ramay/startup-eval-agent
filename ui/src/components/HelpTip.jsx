import React from "react";
import { IxTooltip } from "@siemens/ix-react";
import { iconQuestion } from "@siemens/ix-icons/icons";
import Icon from "./Icon.jsx";

/* A "?" beside a heading that explains it on hover or focus. iX guidance asks every icon-only
   control for a tooltip and an accessible description: the IxTooltip is the visible one, and the
   same text is the button's description, so a screen reader hears it without the shadow DOM. */
export default function HelpTip({ id, label, text }) {
  return (
    <>
      <button type="button" id={id} className="help-btn" aria-label={label} aria-describedby={`${id}-text`}>
        <Icon icon={iconQuestion} size={14} />
      </button>
      <span id={`${id}-text`} className="sr-only">{text}</span>
      <IxTooltip for={`#${id}`}>{text}</IxTooltip>
    </>
  );
}
