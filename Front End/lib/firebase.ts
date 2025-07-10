// lib/firebase.ts
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
import { getAnalytics, isSupported, Analytics } from "firebase/analytics";

// ✅ Your Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyAWS12BhYkoBWmpHfDMFhJNpyw3Zr2uI_s",
  authDomain: "talend-25807.firebaseapp.com",
  projectId: "talend-25807",
  storageBucket: "talend-25807.appspot.com", // fixed .app typo
  messagingSenderId: "421613640243",
  appId: "1:421613640243:web:fa2893fa31530ce119e146",
  measurementId: "G-MMXZSM3PJV"
};

// ✅ Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// ✅ Optional: Analytics only in browser
let analytics: Analytics | undefined;
if (typeof window !== "undefined") {
  isSupported().then((supported) => {
    if (supported) {
      analytics = getAnalytics(app);
    }
  });
}

export { auth, db, analytics };
