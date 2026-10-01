import React from "react";
import { IxContentHeader } from "@siemens/ix-react";
import Section from "../Section.jsx";
import SfsPanel from "./SfsPanel.jsx";

/* Siemens Financial Services: which financing line applies, outside the weighted total. Shown in
   full in both views — "a financing line applies" is a finding a reader should not have to open
   anything to see. The model's own dimension scores used to sit here as diagnostics; they are
   gone, the weighted total and its components being the scores this page reports. The old
   #scoring-sfs and #scoring-breakdown anchors still land here, so shared links keep working. */
export default function Supplementary({ res }) {
  return (
    <Section id="scoring-supplementary">
      <span id="scoring-sfs" className="anchor-alias" aria-hidden="true" />
      <span id="scoring-breakdown" className="anchor-alias" aria-hidden="true" />
      <IxContentHeader headerTitle="SFS financing"
        headerSubtitle="Siemens Financial Services: whether a financing line applies, and which. Not part of the weighted total." />
      <SfsPanel rt={res.routing || {}} />
    </Section>
  );
}
