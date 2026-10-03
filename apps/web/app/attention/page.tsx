"use client";
import {AlertsPanel} from '../../components/alerts-panel';
import {DigestPanel} from '../../components/digest-panel';
import {NotificationPanel} from '../../components/notification-panel';
import {SignOutButton} from '../../components/sign-out-button';
export default function AttentionPage() {
  return <main><a href="/competitions">Back to competitions</a><SignOutButton/><AlertsPanel/><DigestPanel/><NotificationPanel/></main>;
}
