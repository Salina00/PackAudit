"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";

interface Rule {
  rule_id: string;
  rule_citation: string;
  description: string;
  check_type: string;
  severity: string;
  fix_suggestion?: string;
  validation_logic?: any;
}

export default function RulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"all" | "metrology" | "fssai" | "apparel">("all");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/rules")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch rule database.");
        return res.json();
      })
      .then((data) => {
        setRules(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch((err) => {
        setRules([]);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const metrologyRules = rules.filter((r) => !r.rule_id.startsWith("fssai_") && !r.rule_id.startsWith("apparel_"));
  const fssaiRules = rules.filter((r) => r.rule_id.startsWith("fssai_"));
  const apparelRules = rules.filter((r) => r.rule_id.startsWith("apparel_"));

  const displayedRules =
    activeTab === "metrology"
      ? metrologyRules
      : activeTab === "fssai"
      ? fssaiRules
      : activeTab === "apparel"
      ? apparelRules
      : rules;

  return (
    <div className="flex min-h-screen bg-[#0A0A0A] text-[#EDEDED]">
      <Sidebar />

      <main className="flex-1 p-8 space-y-6 overflow-y-auto h-screen">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[#EDEDED] font-mono">
              Statutory Compliance Rules Database (25 Rules)
            </h1>
            <p className="text-sm text-[#737373] mt-1 font-mono">
              Statutory rulebook for Legal Metrology Rules 2011, FSSAI Food Regulations 2020, and Textile Labeling Standards.
            </p>
          </div>

          <div className="flex gap-2">
            <span className="px-3 py-1 rounded bg-[#3B82F6]/10 text-[#3B82F6] font-mono text-xs font-bold">
              12 Legal Metrology
            </span>
            <span className="px-3 py-1 rounded bg-[#10B981]/10 text-[#10B981] font-mono text-xs font-bold">
              6 FSSAI Food
            </span>
            <span className="px-3 py-1 rounded bg-[#EC4899]/10 text-[#EC4899] font-mono text-xs font-bold">
              7 Textile & Apparel
            </span>
          </div>
        </div>

        {/* Tab Filters */}
        <div className="flex gap-2 border-b border-[#262626] pb-3 text-xs font-mono">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === "all"
                ? "bg-[#262626] text-[#EDEDED] font-bold"
                : "text-[#737373] hover:text-[#EDEDED]"
            }`}
          >
            All Rules ({rules.length})
          </button>
          <button
            onClick={() => setActiveTab("metrology")}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === "metrology"
                ? "bg-[#3B82F6]/20 text-[#3B82F6] font-bold"
                : "text-[#737373] hover:text-[#EDEDED]"
            }`}
          >
            Legal Metrology 2011 ({metrologyRules.length})
          </button>
          <button
            onClick={() => setActiveTab("fssai")}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === "fssai"
                ? "bg-[#10B981]/20 text-[#10B981] font-bold"
                : "text-[#737373] hover:text-[#EDEDED]"
            }`}
          >
            FSSAI Food 2020 ({fssaiRules.length})
          </button>
          <button
            onClick={() => setActiveTab("apparel")}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === "apparel"
                ? "bg-[#EC4899]/20 text-[#EC4899] font-bold"
                : "text-[#737373] hover:text-[#EDEDED]"
            }`}
          >
            Apparel & Textile 2011 ({apparelRules.length})
          </button>
        </div>

        {/* Rules Table */}
        {loading ? (
          <div className="text-center py-12 text-[#737373] font-mono text-xs">
            Loading rule database definitions from PostgreSQL...
          </div>
        ) : error ? (
          <div className="p-4 border border-[#DC2626]/20 bg-[#DC2626]/5 rounded text-[#EF4444] font-mono text-xs">
            {error}
          </div>
        ) : (
          <div className="border border-[#262626] bg-[#0F0F0F] rounded overflow-hidden">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-[#262626] bg-[#151515] text-[#A3A3A3] font-bold">
                  <th className="p-3 w-32">Rule Citation</th>
                  <th className="p-3 w-28">Domain</th>
                  <th className="p-3 w-40">Rule Name</th>
                  <th className="p-3">Statutory Description & Auto-Fix Guidance</th>
                  <th className="p-3 w-24">Severity</th>
                  <th className="p-3 w-28">Check Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626]">
                {displayedRules.map((rule) => {
                  const isFssai = rule.rule_id.startsWith("fssai_");
                  const isApparel = rule.rule_id.startsWith("apparel_");
                  return (
                    <tr key={rule.rule_id} className="hover:bg-[#151515] transition">
                      <td className="p-3 font-bold text-[#EDEDED]">{rule.rule_citation}</td>
                      <td className="p-3">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                            isFssai
                              ? "bg-[#10B981]/10 text-[#10B981]"
                              : isApparel
                              ? "bg-[#EC4899]/10 text-[#EC4899]"
                              : "bg-[#3B82F6]/10 text-[#3B82F6]"
                          }`}
                        >
                          {isFssai ? "FSSAI Food" : isApparel ? "Textile" : "Metrology"}
                        </span>
                      </td>
                      <td className="p-3 text-[#A3A3A3]">{rule.rule_id}</td>
                      <td className="p-3 space-y-1">
                        <div className="text-[#C2C2C2] leading-relaxed">{rule.description}</div>
                        {rule.fix_suggestion && (
                          <div className="text-[11px] text-[#10B981] bg-[#10B981]/5 p-1.5 rounded border border-[#10B981]/20">
                            💡 <b>Fix Template:</b> {rule.fix_suggestion}
                          </div>
                        )}
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            rule.severity === "CRITICAL"
                              ? "bg-[#DC2626]/20 text-[#EF4444]"
                              : rule.severity === "MAJOR"
                              ? "bg-[#F59E0B]/20 text-[#F59E0B]"
                              : "bg-[#262626] text-[#737373]"
                          }`}
                        >
                          {rule.severity}
                        </span>
                      </td>
                      <td className="p-3 uppercase text-[#737373] text-[10px]">
                        {rule.check_type}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
