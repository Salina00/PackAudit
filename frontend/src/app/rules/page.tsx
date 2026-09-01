"use client";

import { useEffect, useState } from "react";

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
  const [activeTab, setActiveTab] = useState<"all" | "metrology" | "fssai">("all");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/rules")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch rule database.");
        return res.json();
      })
      .then((data) => {
        setRules(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const metrologyRules = rules.filter((r) => !r.rule_id.startsWith("fssai_"));
  const fssaiRules = rules.filter((r) => r.rule_id.startsWith("fssai_"));

  const displayedRules =
    activeTab === "metrology"
      ? metrologyRules
      : activeTab === "fssai"
      ? fssaiRules
      : rules;

  return (
    <div className="flex-1 p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#EDEDED] font-mono">
            Statutory Compliance Rules Database
          </h1>
          <p className="text-sm text-[#737373] mt-1 font-mono">
            Full statutory rulebook comprising Legal Metrology Rules, 2011 and FSSAI Labelling & Display Regulations, 2020.
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-1.5 p-1 bg-[#0F0F0F] border border-[#262626] rounded text-xs font-mono">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === "all"
                ? "bg-[#10B981] text-[#0A0A0A] font-bold"
                : "text-[#A3A3A3] hover:text-[#EDEDED]"
            }`}
          >
            All Rules ({rules.length})
          </button>
          <button
            onClick={() => setActiveTab("metrology")}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === "metrology"
                ? "bg-[#10B981] text-[#0A0A0A] font-bold"
                : "text-[#A3A3A3] hover:text-[#EDEDED]"
            }`}
          >
            Legal Metrology ({metrologyRules.length})
          </button>
          <button
            onClick={() => setActiveTab("fssai")}
            className={`px-3 py-1.5 rounded transition ${
              activeTab === "fssai"
                ? "bg-[#10B981] text-[#0A0A0A] font-bold"
                : "text-[#A3A3A3] hover:text-[#EDEDED]"
            }`}
          >
            FSSAI Food ({fssaiRules.length})
          </button>
        </div>
      </div>

      {loading ? (
        <div className="border border-[#262626] bg-[#0F0F0F] rounded p-12 text-center text-sm text-[#737373] font-mono">
          Loading statutory parameters from PostgreSQL database...
        </div>
      ) : error ? (
        <div className="border border-[#DC2626]/20 bg-[#DC2626]/5 text-[#EF4444] rounded p-6 text-sm font-mono">
          Error: {error}
        </div>
      ) : (
        <div className="border border-[#262626] bg-[#0F0F0F] rounded overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#262626] bg-[#151515] text-xs font-bold text-[#A3A3A3] font-mono">
                <th className="p-4">Check ID</th>
                <th className="p-4">Statutory Citation</th>
                <th className="p-4">Rule Description & Auto-Fix Guidance</th>
                <th className="p-4">Type</th>
                <th className="p-4">Severity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#262626] text-sm text-[#EDEDED]">
              {displayedRules.map((rule) => (
                <tr key={rule.rule_id} className="hover:bg-[#151515] transition">
                  <td className="p-4 font-mono font-bold text-[#A3A3A3] text-xs">
                    {rule.rule_id}
                  </td>
                  <td className="p-4 font-mono text-xs text-[#10B981] font-semibold max-w-[180px]">
                    {rule.rule_citation}
                  </td>
                  <td className="p-4 max-w-md space-y-1.5">
                    <div className="text-xs text-[#C2C2C2] leading-relaxed">
                      {rule.description}
                    </div>
                    {rule.fix_suggestion && (
                      <div className="text-[11px] text-[#10B981] font-mono bg-[#10B981]/5 border border-[#10B981]/15 rounded p-2 flex items-start gap-1.5">
                        <span className="font-bold shrink-0">💡 Fix Guidance:</span>
                        <span className="leading-snug">{rule.fix_suggestion}</span>
                      </div>
                    )}
                  </td>
                  <td className="p-4 font-mono text-xs text-[#737373] uppercase">
                    {rule.check_type}
                  </td>
                  <td className="p-4">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold font-mono ${
                        rule.severity === "CRITICAL"
                          ? "bg-[#DC2626]/10 text-[#EF4444]"
                          : rule.severity === "MAJOR"
                          ? "bg-[#F59E0B]/10 text-[#F59E0B]"
                          : "bg-[#737373]/10 text-[#A3A3A3]"
                      }`}
                    >
                      {rule.severity}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
