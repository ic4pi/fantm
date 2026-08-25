import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Navbar } from "@/components/Navbar";
import { CustomCursor } from "@/components/CustomCursor";
import { PageTransition } from "@/components/PageTransition";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import CreateBook from "@/pages/CreateBook";
import BookGeneration from "@/pages/BookGeneration";
import BookReader from "@/pages/BookReader";
import Store from "@/pages/Store";
import PaymentSuccess from "@/pages/PaymentSuccess";
import PaymentCancel from "@/pages/PaymentCancel";

function App() {
  return (
    <div className="App min-h-screen">
      <div className="scanlines" />
      <div className="noise-grain" />
      <BrowserRouter>
        <AuthProvider>
          <CustomCursor />
          <Navbar />
          <PageTransition>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/payment/success" element={<PaymentSuccess />} />
              <Route path="/payment/cancel" element={<PaymentCancel />} />
              <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/store" element={<ProtectedRoute><Store /></ProtectedRoute>} />
              <Route path="/books/new" element={<ProtectedRoute><CreateBook /></ProtectedRoute>} />
              <Route path="/books/:id/generating" element={<ProtectedRoute><BookGeneration /></ProtectedRoute>} />
              <Route path="/books/:id/read" element={<ProtectedRoute><BookReader /></ProtectedRoute>} />
            </Routes>
          </PageTransition>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
