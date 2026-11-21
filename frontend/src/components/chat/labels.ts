// Human labels for the case file. Fact keys mirror FACTS in src/lawbuddy/conversation/case.py.

export const CATEGORY_LABEL: Record<string, string> = {
  deposit: 'Security deposit',
  consumer: 'Refund / faulty product or service',
  salary: 'Unpaid salary',
};

export const FACT_LABEL: Record<string, string> = {
  deposit_amount: 'Deposit paid',
  move_out_date: 'Moved out on',
  written_agreement: 'Written rental agreement',
  city: 'City',
  landlord_reason: "Landlord's reason",
  deposit_proof: 'How the deposit was paid',
  product_or_service: 'Product or service',
  seller: 'Seller',
  amount_paid: 'Amount paid',
  purchase_date: 'Bought on',
  problem: 'What went wrong',
  complaint_made: 'Complaint made',
  employer: 'Employer',
  monthly_salary: 'Monthly salary',
  unpaid_period: 'Unpaid period',
  employment_status: 'Employment status',
  proof_of_employment: 'Proof of employment',
};

export const KIND_LABEL: Record<string, string> = {
  guide: 'Guide',
  statute: 'Text of the law',
  practice: 'Practical note',
};

export const factLabel = (key: string) => FACT_LABEL[key] || key.replace(/_/g, ' ');
