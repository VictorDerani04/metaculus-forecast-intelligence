"use client";
import {AlertsPanel} from '../../components/alerts-panel';
import {DigestPanel} from '../../components/digest-panel';
import {NotificationPanel} from '../../components/notification-panel';
export default function AttentionPage() {
  return <main><a href="/competitions">Back to competitions</a><AlertsPanel/><DigestPanel/><NotificationPanel/></main>;
}
